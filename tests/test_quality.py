import io
from copy import deepcopy
from unittest.mock import patch

import pytest
from pypdf import PdfReader

from quality import AnalysisQualityError, filter_feedback, review_analysis
from reporting import build_report_pdf, report_markdown, sections
from sources import gather
from tests.fixtures import single_result,comparison_result


def test_screening_removes_clear_promotion_and_creator_chatter_but_keeps_criticism():
    texts=['Save 25% with my referral link and use my code on your next order.',
           'Excellent video and fantastic review. Thank you for the great content.',
           'Great video. My car has uncomfortable seats and the battery range disappoints.',
           'My referral code is broken and I cannot get a refund for the charge.',
           'I own this product and the setup is frustrating, but support was helpful.']
    items=[{'source':'YouTube','text':t} for t in texts]
    kept,excluded=filter_feedback(items)
    assert [i['text'] for i in kept]==texts[2:]
    assert sum(excluded.values())==2


def test_risky_copy_and_unmatched_wording_are_withheld_without_editing_original():
    result=single_result();data=deepcopy(result['data']);original=deepcopy(data)
    data['headline']='Features drive strong conversion'
    data['angles'] += [dict(data['angles'][0],hook='The quietest cabin in its class'),
                      dict(data['angles'][0],hook='Let FSD handle your winter road trips'),
                      dict(data['angles'][0],hook='A useful idea',customer_words='Words no source actually said')]
    before=deepcopy(data)
    clean,notes=review_analysis(data,result['items'],subject='QA company')
    assert clean['angles']==original['angles'] and data==before
    assert clean['headline']=='Feedback signals to investigate for QA company'
    assert len(notes)==4
    result.update(data=clean,quality_checks=notes,collection={'received':30,'excluded':{'Promotional message':6},'selected':24})
    plain=report_markdown(result);pdf='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(build_report_pdf(result))).pages)
    for text in (plain,pdf):
        assert 'Evidence review notes' in text and 'Source screening: 30 collected items' in text
        assert 'quietest cabin' not in text and 'Let FSD handle' not in text


def test_invalid_references_are_not_treated_as_evidence():
    r=single_result();r['data']['loved'][0]['evidence_ids']=[True,999,0,'1']
    clean,notes=review_analysis(r['data'],r['items'])
    assert clean['loved']==[] and len(notes)==1


def test_comparison_messaging_cannot_borrow_another_brands_quote():
    r=comparison_result();r['data']['angles'][0]['evidence_ids']=[16]
    clean,notes=review_analysis(r['data'],r['items'],'compare')
    assert clean['angles']==[] and any('indicated brand' in x['detail'] for x in notes)


@pytest.mark.parametrize('values',[{'positive':90,'neutral':20,'negative':10}, {'positive':-1,'neutral':51,'negative':50}])
def test_inconsistent_percentages_are_rejected(values):
    r=single_result();r['data']['sentiment']=values
    with pytest.raises(AnalysisQualityError):review_analysis(r['data'],r['items'])


def test_collection_tracks_screening_deduplication_limits_and_safe_errors():
    shared={'source':'YouTube','text':'I own this car and find its seats comfortable for a long journey.'}
    promo={'source':'YouTube','text':'Save 30% with my referral link and use my code to buy.'}
    long_a={'source':'YouTube','text':'I own this product and its important feature works well. '*3+'A different end.'}
    long_b=dict(long_a,text=long_a['text'][:-16]+'Another distinct end.')
    with patch('sources.fetch_youtube',return_value=[shared,promo,shared,long_a,long_b]),patch('sources.fetch_appstore',side_effect=RuntimeError('https://provider.example?key=SECRET')):
        items,status=gather('QA',['YouTube','App Store'],'fake-key',max_items=120)
    assert len(items)==3
    assert status['_quality']['received']==5 and status['_quality']['selected']==3
    assert sum(status['_quality']['excluded'].values())==1
    assert status['App Store']=='unavailable' and 'SECRET' not in str(status)
