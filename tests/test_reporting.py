import io
from copy import deepcopy
from pathlib import Path

import fitz
import pytest
from pypdf import PdfReader

from reporting import build_report_pdf, evidence_ids, exact_quote, public_url, report_filename, report_markdown, sections
from tests.fixtures import comparison_result, single_result


def pdf_text(data):
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)


@pytest.mark.parametrize('make', [single_result, comparison_result])
def test_pdf_contains_complete_analysis_and_source_appendix(make):
    result=make();data=build_report_pdf(result);text=pdf_text(data)
    assert data.startswith(b'%PDF-')
    for title, entries in sections(result):
        assert title in text
        for entry in entries:
            assert entry['title'] in text
    assert 'Source appendix' in text and 'Scope and limitations' in text
    for i in range(1,len(result['items'])+1):assert f'QA source {i}:' in text
    assert 'AI estimates' in text and 'confidence High' not in text
    assert '2026-11-28 10:00 UTC' in text
    assert 'Café' in text and 'β' in text and '₹' in text


def test_pdf_links_resolve_and_escape_untrusted_text():
    result=comparison_result();result['data']['summary']='A <script>alert(1)</script> & "quote" stays plain text.'
    result['items'][0]['url']='javascript:alert(1)'
    data=build_report_pdf(result);reader=PdfReader(io.BytesIO(data));text=pdf_text(data)
    assert '<script>alert(1)</script>' in text
    annotations=[a.get_object() for page in reader.pages for a in page.get('/Annots',[])]
    assert any(a.get('/Subtype')=='/Link' and a.get('/Dest') for a in annotations)
    uris=[str(a.get('/A',{}).get('/URI','')) for a in annotations]
    assert all(not u.startswith('javascript:') for u in uris)
    assert any('&mode=qa' in u for u in uris)


def test_evidence_and_quote_checks_are_exact_and_ordered():
    items=[{'text':'Café is simple.  Easy to use.'}]
    assert evidence_ids([True,0,1,1,2,'1',None],items)==[1]
    assert exact_quote('Café is simple.',[1],items)
    assert exact_quote('Easy to use.',[1],items)
    assert not exact_quote('café is simple',[1],items)
    assert not exact_quote('made up',[1],items)


def test_invalid_angles_are_not_presented_as_supported():
    result=single_result();result['data']['angles'][0]['evidence_ids']=[999]
    assert sections(result)[2][1]==[]
    assert 'No supported item' in pdf_text(build_report_pdf(result))


def test_paraphrases_and_own_feedback_are_labeled_correctly():
    result=single_result();result['data']['angles'][0]['customer_words']='A fictional paraphrase'
    text=pdf_text(build_report_pdf(result));plain=report_markdown(result)
    assert 'not an exact source quote' in text and 'not an exact source quote' in plain
    assert 'Public-source availability' not in text
    assert 'Own feedback' in text and 'AI-estimated share of sample: 100%' in text


def test_long_reports_paginate_without_clipping():
    result=single_result(120)
    result['subject']='QA long title ' * 12
    result['data']['loved'][0]['detail']='Long-form finding and supporting explanation. '*170
    data=build_report_pdf(result);doc=fitz.open(stream=data,filetype='pdf')
    assert len(doc)>8
    for page in doc:
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    x0,y0,x1,y1=span['bbox']
                    assert x0>=40 and x1<=page.rect.width-40
                    assert y0>=20 and y1<=page.rect.height-20
    assert 'QA source 120:' in pdf_text(data)


def test_unavailable_glyphs_have_visible_fallback():
    result=single_result();result['items'][0]['text']='QA emoji 🙂 and CJK 中文'
    text=pdf_text(build_report_pdf(result))
    assert 'Text rendering note' in text and '[U+' in text
    assert '🙂' in report_markdown(result) and '中文' in report_markdown(result)


def test_export_names_and_url_allowlist():
    result=single_result();result['subject']='A / B: unsafe?'
    assert report_filename(result)=='voicebrief-a-b-unsafe-2026-11-28.pdf'
    assert public_url('javascript:alert(1)')==''
    assert public_url('https://example.com/a?b=2')=='https://example.com/a?b=2'
    assert public_url('https://[broken')==''


def test_generate_visual_review_artifacts():
    folder=Path('qa-output');folder.mkdir(exist_ok=True)
    for name,make in [('single',single_result),('comparison',comparison_result)]:
        data=build_report_pdf(make());(folder/(name+'.pdf')).write_bytes(data)
        doc=fitz.open(stream=data,filetype='pdf')
        for i,page in enumerate(doc):page.get_pixmap(matrix=fitz.Matrix(1.25,1.25)).save(folder/f'{name}-{i+1}.png')
