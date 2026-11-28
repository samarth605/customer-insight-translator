from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from streamlit.testing.v1 import AppTest
from tests.fixtures import comparison_result, single_result

APP=Path(__file__).resolve().parents[1]/'app.py'


def app():
    at=AppTest.from_file(APP,default_timeout=25)
    at.secrets['GOOGLE_API_KEY']='qa-fake-key-no-network'
    return at.run()


def fill_own(at,name='QA test company'):
    at.text_input(key='o_name').set_value(name)
    at.text_area(key='o_desc').set_value('A synthetic product for QA only.')
    at.text_area(key='p_raw').set_value('\n'.join(item['text'] for item in single_result()['items']))
    return at


def mock_client(data):
    response = SimpleNamespace(parsed=SimpleNamespace(model_dump=lambda:deepcopy(data)))
    context = AsyncMock()
    context.__aenter__.return_value = SimpleNamespace(models=SimpleNamespace(generate_content=AsyncMock(return_value=response)))
    return SimpleNamespace(aio=context, close=lambda:None)


def test_entry_has_task_before_settings_and_no_key_is_required_for_review():
    at=AppTest.from_file(APP,default_timeout=25).run()
    assert not at.exception
    assert at.get('button_group')[0].value=='Your feedback'
    assert at.text_input(key='o_name').label=='Company or product'
    assert not at.multiselect
    assert not any(s.label=='Review window' for s in at.selectbox)
    assert at.session_state.runs==0


def test_missing_input_never_spends_a_run_or_calls_provider():
    at=app()
    with patch('google.genai.Client') as client:
        at.button(key='p_go').click().run()
        client.assert_not_called()
    assert at.session_state.runs==0
    assert any('company' in w.value.lower() for w in at.warning)


def test_own_generation_pdf_and_evidence_do_not_rerun_analysis():
    at=fill_own(app())
    with patch('google.genai.Client',return_value=mock_client(single_result()['data'])) as client:
        at.button(key='p_go').click().run()
        assert client.call_count==1
        assert not at.exception
        assert at.session_state.runs==1
        assert at.session_state.result['origin']=='own'
        assert at.text_input(key='o_name').value=='QA test company'
        assert at.text_area(key='p_raw').value.count('QA source')==24
        assert at.session_state.pdf_export['bytes'].startswith(b'%PDF-')
        previous=at.session_state.pdf_export['bytes']
        at.button(key='evidence_0_0').click().run()
        assert not at.exception
        assert any('Source 1' in m.value for m in at.markdown)
        assert at.session_state.runs==1 and client.call_count==1
        at.run()
        assert at.session_state.pdf_export['bytes']==previous and client.call_count==1


def test_failure_keeps_previous_report_and_does_not_expose_key():
    at=fill_own(app(),'QA failure company')
    at.session_state.result=single_result();at.run()
    with patch('google.genai.Client',side_effect=RuntimeError('qa-fake-key-no-network')):
        at.button(key='p_go').click().run()
    assert not at.exception and at.session_state.runs==0
    assert at.session_state.result['subject']=='Quality assurance fixture'
    assert any('previous brief is preserved' in e.value for e in at.error)
    assert not any('qa-fake-key' in e.value for e in at.error)


def test_context_failure_requires_description_before_provider_call():
    at=fill_own(app(),'QA unreadable context')
    at.text_area(key='o_desc').set_value('')
    at.text_input(key='o_url').set_value('https://example.com')
    with patch('requests.get',side_effect=RuntimeError('offline')),patch('google.genai.Client') as client:
        at.button(key='p_go').click().run()
        client.assert_not_called()
    assert at.session_state.runs==0
    assert any('could not be read' in w.value for w in at.warning)


def test_public_brand_generation_and_comparison():
    at=app();at.get('button_group')[0].set_value('Brand brief').run()
    at.text_input(key='s_name').set_value('QA Brand A')
    at.session_state['s_q']='QA Brand A';at.session_state['s_cands']=[{'name':'QA Brand A','website':'https://example.com','headquarters':'QA','description':'Synthetic brand'}]
    at.run()
    with patch('sources.gather',return_value=(single_result()['items'],{'QA source':24})),patch('google.genai.Client',return_value=mock_client(single_result()['data'])):
        at.button(key='s_go').click().run()
    assert not at.exception and at.session_state.result['origin']=='public' and at.session_state.runs==1
    old_fingerprint=at.session_state.pdf_export['fingerprint']
    at.get('button_group')[0].set_value('Compare brands').run()
    at.text_input(key='a_name').set_value('QA Brand A');at.text_input(key='b_name').set_value('QA Brand B')
    for prefix,name in [('a','QA Brand A'),('b','QA Brand B')]:
        at.session_state[prefix+'_q']=name;at.session_state[prefix+'_cands']=[{'name':name,'website':'https://example.com','headquarters':'QA','description':'Synthetic brand'}]
    at.run();a=single_result(15)['items'];b=single_result(15)['items']
    with patch('sources.gather',side_effect=[(a,{'QA':15}),(b,{'QA':15})]),patch('google.genai.Client',return_value=mock_client(comparison_result()['data'])):
        at.button(key='c_go').click().run()
    assert not at.exception and at.session_state.runs==2
    assert at.session_state.result['kind']=='compare'
    assert at.session_state.result['counts']==(15,15)
    assert at.session_state.pdf_export['fingerprint']!=old_fingerprint


def test_own_settings_do_not_offer_unrelated_public_sources():
    at=app();at.radio(key='o_mode').set_value('Upload CSV').run()
    assert any(s.label=='Review window' for s in at.selectbox)
    assert not at.multiselect
    at.get('button_group')[0].set_value('Brand brief').run()
    assert at.multiselect(key='public_sources').label=='Public sources'


def test_changed_brand_query_cannot_use_stale_selection():
    at=app();at.get('button_group')[0].set_value('Brand brief').run()
    at.text_input(key='s_name').set_value('New brand')
    at.session_state['s_q']='Old brand';at.session_state['s_cands']=[{'name':'Old brand','website':'https://example.com','headquarters':'QA','description':'Old selection'}]
    at.run()
    assert all(b.key!='s_go' for b in at.button)


def test_find_brand_returns_candidates_without_spending_an_analysis_run():
    at=app();at.get('button_group')[0].set_value('Brand brief').run()
    at.text_input(key='s_name').set_value('Tesla Inc')
    at.text_input(key='s_hint').set_value('USA')
    companies=[{'name':'Tesla, Inc.','website':'tesla.com','headquarters':'Austin, USA','description':'Electric vehicles and energy products'}]
    with patch('google.genai.Client',return_value=mock_client({'companies':companies})) as client:
        at.button(key='s_find').click().run()
        assert client.call_count==1
    assert not at.exception and at.session_state.runs==0
    assert at.radio(key='s_radio').value.startswith('Tesla, Inc.')
    assert any(b.key=='s_go' for b in at.button)


def test_lookup_timeout_clears_old_candidates_and_allows_explicit_manual_choice():
    from gemini_client import ProviderTimeout
    at=app();at.get('button_group')[0].set_value('Brand brief').run()
    at.text_input(key='s_name').set_value('QA timeout brand')
    at.session_state['s_q']='QA timeout brand'
    at.session_state['s_cands']=[{'name':'Old match','website':'example.com','headquarters':'QA','description':'Stale'}]
    with patch('gemini_client.generate_structured',side_effect=ProviderTimeout('secret-provider-details')):
        at.button(key='s_find').click().run()
    assert not at.exception and at.session_state.runs==0
    assert at.session_state['s_cands']==[]
    assert any('took too long' in w.value for w in at.warning)
    assert not any('secret-provider-details' in w.value for w in at.warning)
    assert all(b.key!='s_go' for b in at.button)
    at.checkbox(key='s_manual').check().run()
    assert any(b.key=='s_go' for b in at.button)
    at.text_input(key='s_hint').set_value('different company context').run()
    assert all(b.key!='s_go' for b in at.button)


def test_empty_lookup_has_visible_manual_path_and_no_implicit_selection():
    at=app();at.get('button_group')[0].set_value('Brand brief').run()
    at.text_input(key='s_name').set_value('QA no matching brand')
    with patch('google.genai.Client',return_value=mock_client({'companies':[]})):
        at.button(key='s_find').click().run()
    assert not at.exception and at.session_state.runs==0
    assert at.checkbox(key='s_manual').value is False
    assert all(b.key!='s_go' for b in at.button)


def test_comparison_looks_up_second_brand_even_when_first_lookup_times_out():
    from gemini_client import ProviderTimeout
    at=app();at.get('button_group')[0].set_value('Compare brands').run()
    at.text_input(key='a_name').set_value('QA timeout side A')
    at.text_input(key='b_name').set_value('QA working side B')
    companies=[{'name':'QA working side B','website':'example.com','headquarters':'QA','description':'Synthetic'}]
    with patch('gemini_client.generate_structured',side_effect=[ProviderTimeout('timeout'),({'companies':companies},'QA-model')]) as generate:
        at.button(key='c_find').click().run()
        assert generate.call_count==2
    assert not at.exception and at.session_state.runs==0
    assert at.session_state['a_cands']==[] and at.session_state['b_cands']==companies
    assert at.radio(key='b_radio').value.startswith('QA working side B')
    at.checkbox(key='a_manual').check().run()
    assert any(b.key=='c_go' for b in at.button)


def test_inconsistent_analysis_is_not_saved_or_counted():
    at=fill_own(app(),'QA inconsistent estimates')
    data=single_result()['data'];data['sentiment']={'positive':90,'neutral':90,'negative':10}
    with patch('google.genai.Client',return_value=mock_client(data)):
        at.button(key='p_go').click().run()
    assert not at.exception and at.session_state.runs==0
    assert any('inconsistent estimates' in w.value for w in at.warning)
    assert 'result' not in at.session_state
