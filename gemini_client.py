"""Bounded Gemini requests; one retry policy owns model fallbacks."""

import asyncio
import logging

from google import genai
from google.genai import types


logger = logging.getLogger(__name__)
LOOKUP_TIMEOUT = 25
LOOKUP_REQUEST_TIMEOUT = 10
ANALYSIS_TIMEOUT = 100
ANALYSIS_REQUEST_TIMEOUT = 50


class Busy(Exception):
    """The provider could not serve the request; no analysis run is counted."""


class ProviderTimeout(Busy):
    """The complete operation exceeded its time budget."""


def generate_structured(prompt, api_key, schema, temperature, models, *, lookup=False,
                        total_timeout=None, request_timeout=None):
    """Use cancellable requests with a deadline across all fallback models.

    A transport timeout alone does not bound SDK retries or the complete operation.
    The SDK gets one attempt, and asyncio bounds both each request and the whole
    sequence. Each distinct model is tried at most once. No prompt, key or raw
    provider error is written to logs.
    """
    total_timeout = total_timeout if total_timeout is not None else (LOOKUP_TIMEOUT if lookup else ANALYSIS_TIMEOUT)
    request_timeout = request_timeout if request_timeout is not None else (LOOKUP_REQUEST_TIMEOUT if lookup else ANALYSIS_REQUEST_TIMEOUT)
    return asyncio.run(_generate(prompt, api_key, schema, temperature, models,
                                 lookup, total_timeout, request_timeout))


async def _generate(prompt, api_key, schema, temperature, models, lookup,
                    total_timeout, request_timeout):
    options = types.HttpOptions(timeout=max(1, int(request_timeout * 1000)),
                                retry_options=types.HttpRetryOptions(attempts=1))
    client = genai.Client(api_key=api_key, http_options=options)
    last_error, timed_out, unavailable = None, False, False
    try:
        async with client.aio as aclient:
            try:
                async with asyncio.timeout(total_timeout):
                    for model in dict.fromkeys(models):
                        config = types.GenerateContentConfig(
                            response_mime_type="application/json", response_schema=schema,
                            temperature=temperature)
                        if lookup:
                            config.max_output_tokens = 4096
                            # Keep this small identity lookup out of deep reasoning.
                            if model in ("gemini-3.5-flash-lite", "gemini-3.6-flash"):
                                config.thinking_config = types.ThinkingConfig(thinking_level="minimal")
                            elif model == "gemini-3.8-flash":
                                config.thinking_config = types.ThinkingConfig(thinking_level="low")
                        try:
                            async with asyncio.timeout(request_timeout):
                                resp = await aclient.models.generate_content(
                                    model=model, contents=prompt, config=config)
                            if resp.parsed is not None:
                                data = resp.parsed.model_dump() if hasattr(resp.parsed, "model_dump") else resp.parsed
                                parsed = schema.model_validate(data)
                            else:
                                parsed = schema.model_validate_json(resp.text or "")
                            return parsed.model_dump(), model
                        except Exception as error:
                            last_error = error
                            code = getattr(error, "code", None)
                            kind = type(error).__name__
                            timeout = isinstance(error, TimeoutError) or "timeout" in kind.lower()
                            transient = code in (408, 429, 500, 502, 503, 504) or timeout or kind in (
                                "ConnectError", "NetworkError", "ServerDisconnectedError")
                            logger.warning("Gemini request failed: model=%s code=%s type=%s", model, code, kind)
                            if code == 404:
                                continue  # unavailable model: try the next configured model
                            if transient:
                                timed_out = timed_out or timeout
                                unavailable = True
                                continue  # never multiply SDK retries with another retry loop
                            raise  # invalid key, permission or request: retrying cannot fix it
            except TimeoutError:
                raise ProviderTimeout("The AI request exceeded its time limit") from None
    finally:
        client.close()
    if timed_out:
        raise ProviderTimeout("The AI provider did not respond in time") from None
    if unavailable:
        raise Busy("The AI provider is temporarily unavailable") from None
    if last_error is not None:
        raise last_error
    raise RuntimeError("No Gemini model was configured")
