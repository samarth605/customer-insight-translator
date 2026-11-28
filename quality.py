"""Conservative, transparent checks. These are not semantic fact verification."""
from collections import Counter
from copy import deepcopy
import re
import unicodedata


class AnalysisQualityError(ValueError):
    """An internally inconsistent response should not spend an analysis run."""


PROMO=re.compile(r'\b(referral (?:link|code)|use (?:my |the )?code|save \d+\s*%|discount code|subscribe for more|sponsored by|my affiliate)\b',re.I)
CREATOR=re.compile(r'\b(great|excellent|amazing|fantastic|terrific|best|thorough|comprehensive|well[- ]done|love(?:d)?)\b.{0,45}\b(video|review|channel|content|job|presentation)\b|\b(thank you|thanks|subscribed|skinny jeans|audio during editing)\b',re.I)
EXPERIENCE=re.compile(r'\b(i (?:own|bought|drive|use|ordered|tried|tested|paid|have had)|my (?:car|vehicle|model|app|order|subscription)|price|cost|expensive|cheap|battery|charging|range|comfort|quiet|noise|seat|tire|tyre|brake|pickup|drop[- ]?off|support|service|delivery|setup|feature|privacy|subscription|refund|quality|performance|fsd|software|bug|screen|legroom|sunroof|warranty|reliable|unreliable|problem|difficult|frustrat\w*)\b',re.I)
RISKY_COPY=re.compile(r'\b(quietest|safest|fastest|cheapest|best[- ]in[- ]class|best in (?:the|its) class|risk[- ]free|guaranteed|guarantees|guarantee|zero risk|a fraction of the cost)\b|\b(?:let|trust)\b.{0,40}\b(?:fsd|full self[- ]driving)\b.{0,45}\b(?:handle|drive|take over)\b',re.I)
UNMEASURED_OUTCOME=re.compile(r'\b(?:drive[sn]?|driving|boost[sn]?|increase[sn]?|improve[sn]?)\s+(?:strong\s+)?(?:conversion|conversions|revenue|sales growth)\b',re.I)
UNPROVEN_COMPARATIVE=re.compile(r'\b(unmatched|unrivalled|unrivaled|unsurpassed|outperforms?|market[- ]leading)\b',re.I)
DRIVING_SYSTEM=re.compile(r'\b(fsd|full self[- ]driving|advanced driving assistance|autonomous driving|driver assistance)\b',re.I)
DRIVING_PROMISE=re.compile(r'\b(handle|navigate|safely|safety|confidence|winter|mountain|road trips?|hands[- ]free|all conditions)\b',re.I)


def _risky_messaging(text):
    return bool(RISKY_COPY.search(text) or UNPROVEN_COMPARATIVE.search(text)
                or (DRIVING_SYSTEM.search(text) and DRIVING_PROMISE.search(text)))


def exclusion_reason(item):
    """Remove only recognizable promotion or creator chatter, not mere negativity."""
    text=str(item.get('text') or '')
    if PROMO.search(text) and not re.search(r"\b(broken|refund|charged|unusable|doesn.t work|can.t use|couldn.t use)\b",text,re.I):return 'Promotional message'
    if item.get('source')=='YouTube' and CREATOR.search(text) and not EXPERIENCE.search(text):
        return 'Creator praise or off-topic production comment'
    return ''


def filter_feedback(items):
    kept=[];excluded=Counter()
    for item in items:
        reason=exclusion_reason(item)
        if reason:excluded[reason]+=1
        else:kept.append(item)
    return kept,dict(excluded)


def _ids(value,items):
    return list(dict.fromkeys(i for i in value or [] if type(i) is int and 1<=i<=len(items)))


def _exact(phrase,ids,items):
    norm=lambda s:re.sub(r'\s+',' ',unicodedata.normalize('NFC',str(s))).strip()
    phrase=norm(phrase)
    return bool(phrase) and any(phrase in norm(items[i-1].get('text','')) for i in ids)


def review_analysis(data,items,kind='single',subject='the subject'):
    """Reject invalid percentages; withhold unsupported evidence/copy suggestions.

    The remaining prose is still AI interpretation, not independently verified.
    Return separate review notes rather than disguising removals as model output.
    """
    data=deepcopy(data);notes=[]
    def check_sentiment(values):
        numbers=[values.get(k) for k in ('positive','neutral','negative')]
        if any(type(n) is not int or not 0<=n<=100 for n in numbers) or sum(numbers)!=100:
            raise AnalysisQualityError('The returned sentiment proportions were inconsistent')
    if kind=='compare':
        for key in ('a','b'):check_sentiment(data[key]['sentiment'])
    else:
        check_sentiment(data['sentiment'])
        shares=[p.get('percentage') for p in data.get('personas',[])]
        if shares and (any(type(n) is not int or not 0<=n<=100 for n in shares) or sum(shares)!=100):
            raise AnalysisQualityError('The returned audience proportions were inconsistent')
    if UNMEASURED_OUTCOME.search(data.get('headline','')):
        data['headline']='Feedback signals to investigate for '+subject
        notes.append({'title':'Business outcome was not measured','detail':'The generated headline inferred a conversion or revenue effect from feedback. It was replaced with a neutral description; this sample does not measure business impact.'})
    def supported(entries,label,brand=None):
        kept=[]
        for entry in entries:
            ids=_ids(entry.get('evidence_ids'),items)
            if brand:ids=[i for i in ids if items[i-1].get('brand')==brand]
            if not ids:
                notes.append({'title':label+' withheld','detail':'No valid source reference supported this item.'});continue
            entry['evidence_ids']=ids;kept.append(entry)
        return kept
    if kind=='compare':
        for key in ('a','b'):
            for field in ('strengths','weaknesses'):data[key][field]=supported(data[key].get(field,[]),'Comparison finding',key.upper())
        for field in ('dimensions','gaps'):data[field]=supported(data.get(field,[]),'Comparison finding')
    else:
        for field in ('loved','pain_points','avoid'):data[field]=supported(data.get(field,[]),'Finding')
    angles=[]
    for angle in supported(data.get('angles',[]),'Messaging suggestion'):
        ids=angle['evidence_ids'];reason=''
        if kind=='compare' and any(items[i-1].get('brand')!=angle.get('brand') for i in ids):reason='The cited feedback did not all belong to the indicated brand.'
        elif _risky_messaging(angle.get('hook','')):reason='The suggestion used a comparative, guaranteed or driving-capability claim that public opinions alone cannot establish.'
        elif not _exact(angle.get('customer_words',''),ids,items):reason='The purported customer wording was not an exact phrase in its cited feedback.'
        if reason:notes.append({'title':'Messaging suggestion withheld','detail':reason,'ids':ids})
        else:angles.append(angle)
    data['angles']=angles
    return data,notes


def collection_notes(collection):
    if not collection:return []
    if 'A' in collection or 'B' in collection:
        return [f'Brand {label}: '+note for label in ('A','B') for note in collection_notes(collection.get(label,{}))]
    received=collection.get('received',0);excluded=collection.get('excluded',{});selected=collection.get('selected',0)
    if not received:return []
    removed=sum(excluded.values())
    detail=', '.join(f'{reason}: {n}' for reason,n in excluded.items())
    return [f'Source screening: {received} collected items, {removed} excluded by conservative text rules, {selected} selected after deduplication and item limits.'+(f' Exclusions: {detail}.' if detail else '')+' Screening does not verify authorship, customer status, relevance or truth; other off-topic items may remain.']
