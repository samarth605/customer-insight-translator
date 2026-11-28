import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel

from gemini_client import Busy, ProviderTimeout, generate_structured


class Payload(BaseModel):
    message: str


class APIError(Exception):
    def __init__(self, code):
        self.code=code
        super().__init__('raw-provider-details-with-secret')


def install_client(monkeypatch, outcomes):
    outcomes=iter(outcomes)
    async def generate(**kwargs):
        outcome=next(outcomes)
        if isinstance(outcome,Exception):
            raise outcome
        if callable(outcome):
            return await outcome()
        return outcome
    generate_mock=AsyncMock(side_effect=generate)
    context=AsyncMock()
    context.__aenter__.return_value=SimpleNamespace(models=SimpleNamespace(generate_content=generate_mock))
    client=SimpleNamespace(aio=context,close=Mock())
    factory=Mock(return_value=client)
    monkeypatch.setattr('google.genai.Client',factory)
    return factory,client,generate_mock


def response():
    return SimpleNamespace(parsed=Payload(message='confirmed'),text=None)


def test_success_has_explicit_http_timeout_one_sdk_attempt_and_closes_client(monkeypatch):
    factory,client,generate=install_client(monkeypatch,[response()])
    result,model=generate_structured('prompt','key',Payload,0.1,['gemini-3.5-flash-lite'],lookup=True)
    assert result=={'message':'confirmed'} and model=='gemini-3.5-flash-lite'
    options=factory.call_args.kwargs['http_options']
    assert options.timeout==10000 and options.retry_options.attempts==1
    config=generate.call_args.kwargs['config']
    assert config.max_output_tokens==4096 and config.thinking_config.thinking_level.value=='MINIMAL'
    client.close.assert_called_once()
    client.aio.__aexit__.assert_awaited_once()


@pytest.mark.parametrize('code',[404,429,500,502,503,504])
def test_unavailable_model_gets_one_attempt_then_falls_back(monkeypatch,code):
    _,client,generate=install_client(monkeypatch,[APIError(code),response()])
    result,model=generate_structured('prompt','key',Payload,0.1,['first','first','second'])
    assert result['message']=='confirmed' and model=='second'
    assert [c.kwargs['model'] for c in generate.call_args_list]==['first','second']
    client.close.assert_called_once()


@pytest.mark.parametrize('code',[400,401,403])
def test_invalid_key_permission_or_request_is_not_retried(monkeypatch,code):
    _,client,generate=install_client(monkeypatch,[APIError(code)])
    with pytest.raises(APIError):
        generate_structured('prompt','key',Payload,0.1,['first','second'])
    assert generate.call_count==1
    client.close.assert_called_once()


def test_overload_never_retries_each_model_or_logs_provider_details(monkeypatch,caplog):
    _,client,generate=install_client(monkeypatch,[APIError(429),APIError(503),APIError(429)])
    with pytest.raises(Busy):
        generate_structured('private-prompt','private-key',Payload,0.1,['a','b','c'])
    assert generate.call_count==3
    assert 'private-prompt' not in caplog.text and 'private-key' not in caplog.text
    assert 'raw-provider-details' not in caplog.text
    client.close.assert_called_once()


def test_hanging_request_is_cancelled_and_next_model_can_succeed(monkeypatch):
    cancelled=[]
    async def hang():
        try: await asyncio.sleep(60)
        finally: cancelled.append(True)
    _,_,generate=install_client(monkeypatch,[hang,response()])
    started=time.monotonic()
    result,model=generate_structured('prompt','key',Payload,0.1,['slow','working'],
                                     total_timeout=0.3,request_timeout=0.025)
    assert result['message']=='confirmed' and model=='working'
    assert cancelled==[True] and generate.call_count==2
    assert time.monotonic()-started<0.5


def test_total_deadline_cancels_inflight_fallback_before_other_models(monkeypatch):
    cancelled=[]
    async def hang():
        try: await asyncio.sleep(60)
        finally: cancelled.append(True)
    _,client,generate=install_client(monkeypatch,[hang,hang,hang])
    started=time.monotonic()
    with pytest.raises(ProviderTimeout):
        generate_structured('prompt','key',Payload,0.1,['a','b','c'],
                            total_timeout=0.07,request_timeout=0.05)
    assert generate.call_count==2 and cancelled==[True,True]
    assert time.monotonic()-started<0.5
    client.close.assert_called_once()
    client.aio.__aexit__.assert_awaited_once()


def test_all_request_timeouts_end_in_friendly_timeout(monkeypatch):
    _,_,generate=install_client(monkeypatch,[TimeoutError(),TimeoutError()])
    with pytest.raises(ProviderTimeout):
        generate_structured('prompt','key',Payload,0.1,['a','b'])
    assert generate.call_count==2


def test_real_sdk_transport_is_cancelled_and_structured_fallback_is_parsed(monkeypatch):
    """Exercise SDK serialization, HTTP transport and parsing without external I/O."""
    import httpx2
    from google import genai

    real_client=genai.Client
    requests=[]
    cancelled=[]
    async def handler(request):
        requests.append(str(request.url))
        if len(requests)==1:
            try: await asyncio.sleep(60)
            finally: cancelled.append(True)
        return httpx2.Response(200,json={
            'candidates':[{'content':{'role':'model','parts':[{'text':'{"message":"confirmed"}'}]},
                           'finishReason':'STOP'}]})
    def factory(**kwargs):
        kwargs['http_options'].httpx_async_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        return real_client(**kwargs)
    monkeypatch.setattr('google.genai.Client',factory)
    started=time.monotonic()
    result,model=generate_structured('QA prompt','fake-key-no-network',Payload,0.1,
                                    ['gemini-3.5-flash-lite','gemini-3.6-flash'],lookup=True,
                                    total_timeout=3,request_timeout=0.05)
    assert result=={'message':'confirmed'} and model=='gemini-3.6-flash'
    assert cancelled==[True] and len(requests)==2
    assert time.monotonic()-started<4
