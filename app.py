import html
import ipaddress
import json
import random
import re
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from sources import gather

APP_NAME = "VoiceBrief"
st.set_page_config(page_title=f"{APP_NAME} | customer voice to strategy brief", page_icon="📝", layout="wide")

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,800&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap');
:root{--paper:#F6F1E7;--card:#FBF8F1;--ink:#1B1B1B;--muted:#6B665C;--line:#D9D0BC;--accent:#B4472A;--olive:#5B6B4F;--sand:#CDBF9F;}
.stApp{background:var(--paper);}
html,body,.stApp,[class*="css"]{font-family:'Inter',system-ui,sans-serif;color:var(--ink);}
#MainMenu,footer,header{visibility:hidden;}
.block-container{max-width:1020px;padding-top:2rem;padding-bottom:4rem;}
.mast{font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:.6rem;}
h1.hero{font-family:'Fraunces',Georgia,serif;font-weight:800;font-size:2.7rem;line-height:1.08;margin:0 0 .6rem 0;letter-spacing:-.02em;}
.sub{color:var(--muted);max-width:660px;font-size:1.02rem;margin-bottom:1.6rem;}
.brief{background:var(--card);border:1px solid var(--line);padding:2.2rem 2.6rem;margin-top:1.6rem;box-shadow:0 1px 0 var(--line),0 10px 30px -18px rgba(0,0,0,.25);}
.brief .meta{font-family:'IBM Plex Mono',monospace;font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:.8rem;margin-bottom:1.4rem;}
.brief h2.hl{font-family:'Fraunces',serif;font-weight:600;font-size:1.9rem;line-height:1.2;margin:0 0 .8rem 0;}
.lede{font-size:1.02rem;line-height:1.6;color:#33302B;margin-bottom:1rem;}
.bar{display:flex;height:9px;overflow:hidden;background:var(--line);}
.bar span{display:block;height:100%;}
.barkey{font-family:'IBM Plex Mono',monospace;font-size:.7rem;color:var(--muted);margin-top:.4rem;}
.sec{margin-top:2.2rem;}
.sec-h{display:flex;align-items:baseline;gap:.8rem;border-top:2px solid var(--ink);padding-top:.7rem;margin-bottom:1rem;}
.sec-h .num{font-family:'IBM Plex Mono',monospace;font-size:.75rem;color:var(--accent);}
.sec-h h2{font-family:'Fraunces',serif;font-size:1.35rem;font-weight:600;margin:0;}
.pt{padding:.7rem 0;border-bottom:1px dashed var(--line);}
.pt-t{font-weight:600;margin-bottom:.2rem;}
.pt-d{color:#47433C;font-size:.95rem;line-height:1.55;}
.rcs{margin-top:.35rem;}
.rc{font-family:'IBM Plex Mono',monospace;font-size:.68rem;color:var(--accent);margin-right:.8rem;text-decoration:none;}
a.rc:hover{text-decoration:underline;}
.tag{font-family:'IBM Plex Mono',monospace;font-size:.65rem;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);padding:.08rem .4rem;margin-left:.4rem;color:var(--muted);}
.tag.high{color:var(--accent);border-color:var(--accent);}
.tag.medium{color:#8A6A12;border-color:#8A6A12;}
.tag.low{color:var(--olive);border-color:var(--olive);}
.tag.ok{color:var(--olive);border-color:var(--olive);}
.angle{display:grid;grid-template-columns:1.5fr 1fr;gap:1.6rem;padding:1rem 0;border-bottom:1px dashed var(--line);}
.hook{font-family:'Fraunces',serif;font-size:1.25rem;font-weight:600;line-height:1.25;margin-bottom:.4rem;}
.note{border-left:3px solid var(--accent);padding-left:.9rem;font-family:'Fraunces',serif;font-style:italic;color:#47433C;font-size:.98rem;}
.notek{font-style:normal;margin-top:.4rem;}
.cols2{display:grid;grid-template-columns:1fr 1fr;gap:2rem;}
.bn{font-family:'Fraunces',serif;font-size:1.3rem;font-weight:600;margin-bottom:.5rem;}
.dim{display:grid;grid-template-columns:150px 110px 1fr;gap:1rem;padding:.7rem 0;border-bottom:1px dashed var(--line);align-items:start;}
.edge{font-family:'IBM Plex Mono',monospace;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--accent);}
.gap{border:1px solid var(--line);background:#FFF9EC;padding:1rem 1.2rem;margin-bottom:.9rem;}
.warn{border:1px solid var(--accent);color:var(--accent);padding:.6rem .9rem;font-size:.85rem;margin-bottom:1rem;}
.stButton>button{background:var(--ink);border:0;border-radius:2px;font-family:'IBM Plex Mono',monospace;letter-spacing:.04em;}
.stButton>button p{color:var(--paper);}
.stButton>button:hover{background:var(--accent);}
.stTabs [data-baseweb="tab"]{font-family:'IBM Plex Mono',monospace;font-size:.8rem;}
html,body{background:var(--paper)!important;}
:root{color-scheme:light;}
.stApp{color-scheme:light;}
[data-testid="stWidgetLabel"] p,[data-testid="stWidgetLabel"] label,[data-testid="stWidgetLabel"] span{color:var(--ink)!important;font-weight:500;}
[data-testid="stTab"],[data-testid="stTab"] *{color:var(--muted)!important;opacity:1!important;}
[data-testid="stTab"]:hover,[data-testid="stTab"]:hover *{color:var(--ink)!important;}
[data-testid="stTab"][aria-selected="true"],[data-testid="stTab"][aria-selected="true"] *{color:var(--accent)!important;}
.stTabs [data-baseweb="tab"] p{color:var(--muted)!important;}
.stTabs [aria-selected="true"] p{color:var(--accent)!important;}
.stTextInput input,.stTextArea textarea{background:#fff!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="textarea"]{background:#fff!important;border:1px solid var(--line)!important;border-radius:2px!important;box-shadow:none!important;}
[data-testid$="RootElement"]{background:#fff!important;border:1px solid var(--line)!important;border-radius:2px!important;box-shadow:none!important;}
[data-testid="stSelectbox"] [role="group"],[data-testid="stMultiSelect"] [role="group"]{background:#fff!important;border:1px solid var(--line)!important;border-radius:2px!important;box-shadow:none!important;}
[data-testid="stSelectbox"] input,[data-testid="stMultiSelect"] input{background:transparent!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[data-testid="stSelectbox"] button,[data-testid="stSelectbox"] svg,[data-testid="stMultiSelect"] button,[data-testid="stMultiSelect"] svg{color:var(--ink)!important;fill:var(--ink)!important;}
[data-baseweb="select"]>div{background:#fff!important;border:1px solid var(--line)!important;border-radius:2px!important;}
[data-baseweb="select"] div,[data-baseweb="select"] span,[data-baseweb="select"] input{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[data-baseweb="select"] svg{fill:var(--ink)!important;}
[data-tag],[data-baseweb="tag"]{background:var(--accent)!important;}
[data-tag] *,[data-baseweb="tag"] *{color:#fff!important;fill:#fff!important;-webkit-text-fill-color:#fff!important;}
[data-testid$="VirtualDropdown"],[data-baseweb="popover"] ul,[data-baseweb="menu"]{background:#fff!important;border:1px solid var(--line)!important;}
[role="listbox"],[role="option"]{background:transparent!important;color:var(--ink)!important;}
[role="option"] *,[data-baseweb="popover"] li{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[role="option"]:hover,[role="option"][data-selected="true"],[role="option"][data-focused="true"],[data-baseweb="popover"] li:hover{background:var(--paper)!important;}
[data-testid="stRadioOption"] > div > div:first-child{background:#fff!important;border:1.5px solid var(--muted)!important;}
[data-testid="stRadioOption"][data-selected="true"] > div > div:first-child{background:var(--accent)!important;border-color:var(--accent)!important;}
[data-testid="stRadio"] label p,[data-testid="stRadioOption"] p{color:var(--ink)!important;}
input::placeholder,textarea::placeholder{color:#9A9488!important;-webkit-text-fill-color:#9A9488!important;opacity:1!important;}
[data-testid="stExpander"]{background:var(--card);border:1px solid var(--line);border-radius:2px;}
[data-testid="stExpander"] summary p,[data-testid="stExpander"] summary span{color:var(--ink)!important;}
[data-testid="stExpander"] details,[data-testid="stExpander"] summary,[data-testid="stExpander"] summary:hover,[data-testid="stExpander"] summary:focus,[data-testid="stExpander"] details[open]>summary{background:var(--card)!important;color:var(--ink)!important;}
[data-testid="stExpander"] summary svg{color:var(--ink)!important;fill:var(--ink)!important;}
.brief a.rc,.stApp a.rc{color:var(--accent)!important;}
[data-testid="stCaptionContainer"]{opacity:1!important;}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{color:var(--muted)!important;}
[data-testid="stMetric"] *,[data-testid="stSpinner"] *{color:var(--ink)!important;}
[data-testid="stTickBar"] *{color:var(--muted)!important;}
[data-testid="stSlider"] [data-testid="stThumbValue"]{color:var(--accent)!important;}
[data-testid="stAlertContainer"]{background:#FFF9EC!important;border:1px solid var(--line)!important;border-left:4px solid var(--sand)!important;border-radius:2px!important;}
[data-testid="stAlertContainer"] *{color:var(--ink)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]){background:#FBEAE5!important;border-left-color:var(--accent)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]){background:#FFF4D6!important;border-left-color:#C9A227!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]){background:#EEF3EA!important;border-left-color:var(--olive)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]){background:#EAF2E3!important;border-left-color:var(--olive)!important;}
[data-testid="stTooltipIcon"] svg,[data-testid="stTooltipIcon"] button{color:var(--muted)!important;stroke:var(--muted)!important;opacity:1!important;}
[data-testid="stTooltipContent"],[data-baseweb="tooltip"] div{background:#fff!important;color:var(--ink)!important;border:1px solid var(--line)!important;}
[data-testid="stTooltipContent"] *{color:var(--ink)!important;}
[data-testid="stFileUploader"] section,[data-testid="stFileUploaderDropzone"]{background:#fff!important;border:1px dashed var(--line)!important;}
[data-testid="stFileUploader"] *{color:var(--ink)!important;}
[data-testid="stFileUploader"] button{background:var(--ink)!important;}
[data-testid="stFileUploader"] button *{color:var(--paper)!important;}
.stDownloadButton>button,[data-testid="stDownloadButton"] button{background:var(--ink)!important;border:0!important;border-radius:2px!important;font-family:'IBM Plex Mono',monospace;}
.stDownloadButton>button *,[data-testid="stDownloadButton"] button *{color:var(--paper)!important;}
.callout{background:#FFF9EC;border:1px solid var(--accent);padding:.9rem 1.1rem;font-size:.92rem;margin-bottom:1rem;line-height:1.5;}
.quota{font-family:'IBM Plex Mono',monospace;font-size:.78rem;border:1px solid var(--ink);background:var(--card);padding:.55rem .9rem;margin-bottom:1rem;display:block;width:100%;box-sizing:border-box;}
.quota .dots{color:var(--accent);letter-spacing:.2em;margin-right:.5rem;}
.quota .qdim{color:var(--muted);}
@media(max-width:760px){.angle,.cols2,.dim{grid-template-columns:1fr;}.brief{padding:1.4rem 1.2rem;}h1.hero{font-size:2rem;}}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)


# ── Secrets & settings ─────────────────────────────────────────────────────────
def secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return None


GOOGLE_KEY = secret("GOOGLE_API_KEY")
YT_KEY = secret("YOUTUBE_API_KEY")
SB_URL = (secret("SUPABASE_URL") or "").rstrip("/")
SB_KEY = secret("SUPABASE_KEY")
if not GOOGLE_KEY:
    st.error("GOOGLE_API_KEY missing. Add it in Streamlit Secrets.")
    st.stop()

# Override without redeploying: add GEMINI_MODEL = "..." in Streamlit Secrets.
PRIMARY_MODEL = secret("GEMINI_MODEL") or "gemini-3.8-flash"
FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]
MAX_ITEMS = 120
SESSION_LIMIT = 5   # free runs per visitor (every brief or comparison = 1 run)
DAILY_LIMIT = 150   # free analyses per day across everyone

depth_map = {
    "Quick Scan": "Be brief: 2-3 points per section, 3 messaging angles.",
    "Standard": "Be balanced: 3-5 points per section, 4 messaging angles.",
    "Deep Dive": "Be thorough: 5+ points per section, 5 messaging angles.",
}


# ── Schemas (Gemini must return exactly these) ─────────────────────────────────
class Sentiment(BaseModel):
    positive: int
    neutral: int
    negative: int


class Point(BaseModel):
    title: str
    detail: str
    evidence_ids: list[int] = Field(description="Numbers of supporting items, max 3")


class PainPoint(BaseModel):
    title: str
    detail: str = Field(description="What customers say went wrong")
    cause: str = Field(description="Root cause as customers describe it")
    severity: Literal["High", "Medium", "Low"]
    evidence_ids: list[int]


class Angle(BaseModel):
    hook: str = Field(description="A message a marketer could run, under 15 words")
    why: str = Field(description="Why it should land, grounded in the data")
    customer_words: str = Field(description="Short phrase (under 12 words) copied exactly from a cited item")
    channel: Literal["Ad", "Landing page", "Sales", "Product", "Social"]
    evidence_ids: list[int]


class Avoid(BaseModel):
    claim: str = Field(description="A claim or tone to avoid")
    reason: str
    evidence_ids: list[int]


class Persona(BaseModel):
    name: str
    description: str
    percentage: int


class Recommendation(BaseModel):
    title: str
    action: str
    priority: Literal["High", "Medium", "Low"]


class Brief(BaseModel):
    headline: str = Field(description="One-sentence verdict a marketing lead can repeat")
    summary: str = Field(description="2 sentences on overall sentiment and why")
    sentiment: Sentiment
    loved: list[Point]
    pain_points: list[PainPoint]
    angles: list[Angle]
    avoid: list[Avoid]
    personas: list[Persona]
    recommendations: list[Recommendation]


class BrandSide(BaseModel):
    sentiment: Sentiment
    strengths: list[Point]
    weaknesses: list[Point]


class Dimension(BaseModel):
    dimension: str = Field(description="A decision factor customers care about, e.g. price, support, range")
    edge: Literal["A", "B", "Even"]
    verdict: str
    evidence_ids: list[int]


class Gap(BaseModel):
    gap: str = Field(description="The positioning opportunity in one line")
    kind: Literal["Open territory", "Competitor weakness"]
    for_brand: Literal["A", "B", "Either"]
    rationale: str
    move: str = Field(description="A concrete marketing move")
    confidence: Literal["High", "Medium", "Low"]
    evidence_ids: list[int]


class AngleX(Angle):
    brand: Literal["A", "B"]


class Comparison(BaseModel):
    headline: str
    summary: str
    a: BrandSide
    b: BrandSide
    dimensions: list[Dimension]
    gaps: list[Gap]
    angles: list[AngleX]


class Candidate(BaseModel):
    name: str
    website: str
    headquarters: str
    description: str = Field(description="One short line on what the company does")


class Candidates(BaseModel):
    companies: list[Candidate]


SCHEMAS = {"brief": Brief, "compare": Comparison}


# ── Gemini helpers ─────────────────────────────────────────────────────────────
class Busy(Exception):
    """Gemini is overloaded (503/429). Not the user's fault; the run is not counted."""


def _call_gemini(prompt, api_key, schema, temperature):
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=schema, temperature=temperature)
    last_err, overloaded = None, False
    for model in dict.fromkeys([PRIMARY_MODEL, *FALLBACK_MODELS]):
        for attempt in range(3):
            try:
                resp = client.models.generate_content(model=model, contents=prompt, config=config)
                parsed = resp.parsed or schema.model_validate_json(resp.text)
                return parsed.model_dump(), model
            except Exception as e:  # noqa: BLE001
                last_err, msg = e, str(e)
                if "404" in msg or "NOT_FOUND" in msg:
                    break  # model gone: try the next one
                if any(c in msg for c in ("429", "500", "503", "UNAVAILABLE", "overloaded", "DEADLINE")):
                    overloaded = True
                    time.sleep(2 + 3 * attempt + random.random())  # back off, then retry
                    continue
                raise
    if overloaded:
        raise Busy("Gemini is overloaded")
    raise last_err


@st.cache_data(show_spinner=False, ttl=3600)
def run_analysis(prompt, api_key, kind):
    return _call_gemini(prompt, api_key, SCHEMAS[kind], 0.4)


@st.cache_data(show_spinner=False, ttl=3600)
def find_companies(name, hint, api_key):
    prompt = (f"List up to 4 distinct real companies or brands named or closely matching '{name}'"
              f"{' (hint: ' + hint + ')' if hint else ''}. Include website domain and headquarters. "
              "Only include ones you are confident exist; return fewer rather than guess.")
    data, _ = _call_gemini(prompt, api_key, Candidates, 0.1)
    return data["companies"]


RULES = """Rules:
- Write for a marketing lead who will act on this. Be specific and plain, no buzzwords.
- Ground every point in the numbered items. Never invent facts. Ignore items about a different company with a similar name.
- Every point, pain point, angle and avoid-item must cite 1-3 item numbers in evidence_ids.
- customer_words must be copied exactly from a cited item (under 12 words).
- Percentages: sentiment must sum to 100; personas must sum to 100."""


def build_brief_prompt(industry, subject, desc, body, depth, own=False):
    own_rule = ("\nThis is the company's OWN customer feedback (CRM, survey or support). Write for its marketing lead: "
                "'Say this' is messaging for its own campaigns, 'Next moves' is what to fix or double down on. "
                "Use the company context to judge what matters.\n") if own else ""
    return f"""You are a senior brand strategist in the {industry} industry writing a one-page brief.

Subject: {subject}{' - ' + desc if desc else ''}
Turn the customer feedback below into a brief: what customers value, what is going wrong and why, messaging angles that use customers' own words, and claims to avoid.

{own_rule}
{RULES}
- {depth_map[depth]} Give 2-4 avoid-items.

Feedback (numbered):
{body}"""


def build_compare_prompt(industry, a, b, body, depth, na, nb):
    thin = (f"\n- Data is thin (A: {na} items, B: {nb} items). Mark gaps Low confidence unless several items support them."
            if min(na, nb) < 15 else "")
    return f"""You are a senior brand strategist in the {industry} industry comparing two brands for a marketing lead.

Brand A = {a[0]}{' - ' + a[1] if a[1] else ''}
Brand B = {b[0]}{' - ' + b[1] if b[1] else ''}
Each item below is tagged with its brand. Use the codes "A" and "B" in edge, for_brand and brand fields.

Deliver: head-to-head on 5-7 decision factors customers care about, 3-5 positioning gaps (open territory nobody owns, or a competitor weakness to exploit, with a concrete marketing move), strengths and weaknesses per brand, and 2-3 messaging angles per brand.

{RULES}
- A gap must cite items. Say "Even" when evidence is balanced; never force a winner.{thin}
- {depth_map[depth]}

Feedback (numbered, brand-tagged):
{body}"""


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}")


def redact(t):
    """Mask emails and common phone formats before text leaves the app."""
    return PHONE_RE.sub("[phone]", EMAIL_RE.sub("[email]", str(t)))


def _public_host(host):
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def _strip(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_page_context(url):
    """Read a company page's title, description and headlines. Public hosts only. Returns '' on any problem."""
    try:
        u = urlparse(url if "://" in url else "https://" + url)
        for _ in range(3):  # follow a few redirects, re-checking the host each time
            if u.scheme not in ("http", "https") or not u.hostname or not _public_host(u.hostname):
                return ""
            r = requests.get(u.geturl(), timeout=8, stream=True, allow_redirects=False,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; VoiceBrief)"})
            if r.is_redirect and r.headers.get("Location"):
                u = urlparse(requests.compat.urljoin(u.geturl(), r.headers["Location"]))
                continue
            break
        else:
            return ""
        raw = b""
        for chunk in r.iter_content(65536):
            raw += chunk
            if len(raw) > 300_000:
                break
        t = raw.decode(r.encoding or "utf-8", errors="replace")
        title = _strip((re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I) or [None, ""])[1])
        metas = []
        for m in re.findall(r"<meta\s[^>]*>", t, re.I):
            nm = re.search(r"(?:name|property)=[\"']([^\"']+)", m, re.I)
            ct = re.search(r"content=[\"']([^\"']*)", m, re.I)
            if nm and ct and nm.group(1).lower() in ("description", "og:description"):
                metas.append(_strip(ct.group(1)))
        heads = [_strip(h) for h in re.findall(r"<h[12][^>]*>(.*?)</h[12]>", t, re.S | re.I)[:6]]
        out = f"Company page title: {title}. Description: {' '.join(metas[:2])}. Headlines: {' | '.join(h for h in heads if h)}."
        return out[:1200] if (title or metas or heads) else ""
    except Exception:
        return ""


# ── Usage logging + caps (Supabase optional; falls back to in-memory) ──────────
def _sbh(extra=None):
    # sb_publishable_ keys are not JWTs: send on apikey only, never as Bearer.
    return {"apikey": SB_KEY, "Content-Type": "application/json", **(extra or {})}


@st.cache_resource
def _mem():
    return {"day": "", "n": 0}


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def runs_today():
    if SB_URL and SB_KEY:
        try:
            r = requests.get(f"{SB_URL}/rest/v1/runs?select=id&created_at=gte.{_today()}T00:00:00Z",
                             headers=_sbh({"Prefer": "count=exact", "Range": "0-0"}), timeout=6)
            return int(r.headers["Content-Range"].split("/")[-1])
        except Exception:
            pass
    m = _mem()
    return m["n"] if m["day"] == _today() else 0


def log_run(subject, n_reviews, sources, seconds, mode):
    m = _mem()
    if m["day"] != _today():
        m["day"], m["n"] = _today(), 0
    m["n"] += 1
    if SB_URL and SB_KEY:
        try:
            r = requests.post(f"{SB_URL}/rest/v1/runs", headers=_sbh({"Prefer": "return=minimal"}), timeout=6,
                              json={"session_id": st.session_state.sid, "company": subject[:80],
                                    "n_reviews": n_reviews, "sources": sources, "seconds": round(seconds, 1),
                                    "mode": mode})
            st.session_state.sb_err = f"{r.status_code}: {r.text[:200]}" if r.status_code >= 300 else ""
        except Exception as e:
            st.session_state.sb_err = f"{type(e).__name__}: {str(e)[:200]}"


@st.cache_data(ttl=300, show_spinner=False)
def sb_stats():
    if not (SB_URL and SB_KEY):
        return None
    try:
        r = requests.get(f"{SB_URL}/rest/v1/runs?select=session_id,n_reviews,seconds&limit=10000",
                         headers=_sbh(), timeout=6)
        rows = r.json()
        if not rows:
            return None
        secs = [x["seconds"] for x in rows if x.get("seconds")]
        return {"runs": len(rows), "visitors": len({x["session_id"] for x in rows}),
                "reviews": sum(x.get("n_reviews") or 0 for x in rows),
                "avg_secs": round(sum(secs) / len(secs), 1) if secs else 0}
    except Exception:
        return None


# ── Rendering helpers (every model/API string goes through E) ──────────────────
def E(x):
    return html.escape(str(x if x is not None else ""))


def show_error(e):
    if isinstance(e, Busy):
        st.info("⏳ Google's AI is swamped right now (their side, not yours). This run wasn't counted. "
                "Try again in a minute, or add your own free Gemini key above.")
    else:
        st.error(f"Something went wrong: {e}")


def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def verbatim(phrase, ids, items):
    p = norm(phrase)
    return bool(p) and any(p in norm(items[i - 1]["text"]) for i in ids or [] if 1 <= i <= len(items))


def has_evidence(ids, n):
    return any(isinstance(i, int) and 1 <= i <= n for i in ids or [])


def rcpts(ids, items):
    out = []
    for i in ids or []:
        if isinstance(i, int) and 1 <= i <= len(items):
            it = items[i - 1]
            if it.get("url", "").startswith("http"):
                out.append(f'<a class="rc" href="{E(it["url"])}" target="_blank">↗ {E(it["source"])} #{i}</a>')
            else:
                out.append(f'<span class="rc">#{i}</span>')
    return f'<div class="rcs">{"".join(out)}</div>' if out else ""


def conf_of(n, hi=60, mid=20):
    return "High" if n >= hi else "Medium" if n >= mid else "Low"


def sec(num, title, body):
    return (f'<div class="sec"><div class="sec-h"><span class="num">{num}</span><h2>{E(title)}</h2></div>'
            f'{body}</div>')


def tag(text, cls=""):
    return f'<span class="tag {cls}">{E(text)}</span>'


def bar(s):
    p, n, g = int(s["positive"]), int(s["neutral"]), int(s["negative"])
    return (f'<div class="bar"><span style="width:{p}%;background:var(--olive)"></span>'
            f'<span style="width:{n}%;background:var(--sand)"></span>'
            f'<span style="width:{g}%;background:var(--accent)"></span></div>'
            f'<div class="barkey">{p}% positive · {n}% neutral · {g}% negative</div>')


def point_html(title, detail, ids, items, extra="", badge=""):
    return (f'<div class="pt"><div class="pt-t">{E(title)}{badge}</div><div class="pt-d">{E(detail)}</div>'
            f'{extra}{rcpts(ids, items)}</div>')


def angle_html(a, items, brand=""):
    ids = a.get("evidence_ids", [])
    ver = tag("✓ verbatim", "ok") if verbatim(a["customer_words"], ids, items) else tag("paraphrase")
    return (f'<div class="angle"><div><div class="hook">{E(a["hook"])}</div>'
            f'<div class="pt-d">{E(a["why"])}</div><div style="margin-top:.5rem">'
            f'<span class="tag" style="margin-left:0">{E(a["channel"])}</span>{brand}</div></div>'
            f'<div class="note">“{E(a["customer_words"])}”<div class="notek">{ver}</div>{rcpts(ids, items)}</div></div>')


def drawer(items, with_brand=False):
    if not items:
        return
    with st.expander(f"📎 The {len(items)} items behind this brief"):
        rows = []
        for i, it in enumerate(items, 1):
            b = tag("Brand " + it["brand"]) if with_brand and it.get("brand") else ""
            rows.append(f'<div class="pt"><span class="rc">#{i}</span>{b}{tag(it["source"])}'
                        f'{tag(it.get("date") or "n/a")}<div class="pt-d">{E(it["text"][:300])}</div></div>')
        st.markdown("".join(rows), unsafe_allow_html=True)


def render_single(res):
    d, items = res["data"], res["items"]
    n = len(items)
    meta = (f'{E(res["subject"])} · {E(res["industry"])} · {E(res["window"] or "your data")} · '
            f'{n} items · confidence {conf_of(n)}')
    angles = [a for a in d["angles"] if has_evidence(a["evidence_ids"], n)]
    h = [f'<div class="brief"><div class="meta">{meta}</div>',
         f'<h2 class="hl">{E(d["headline"])}</h2><div class="lede">{E(d["summary"])}</div>{bar(d["sentiment"])}']
    if n < 20:
        h.append('<div class="warn" style="margin-top:1rem">Small sample. Treat this as directional.</div>')
    h.append(sec("01", "What customers value",
                 "".join(point_html(p["title"], p["detail"], p["evidence_ids"], items) for p in d["loved"])))
    h.append(sec("02", "What's going wrong", "".join(
        point_html(p["title"], p["detail"], p["evidence_ids"], items,
                   extra=f'<div class="pt-d"><b>Root cause:</b> {E(p["cause"])}</div>',
                   badge=tag(p["severity"], p["severity"].lower())) for p in d["pain_points"])))
    h.append(sec("03", "Say this", "".join(angle_html(a, items) for a in angles)
                 or '<div class="pt-d">No angle met the evidence bar. Add more data.</div>'))
    h.append(sec("04", "Avoid saying", "".join(
        point_html(a["claim"], a["reason"], a["evidence_ids"], items) for a in d["avoid"])))
    h.append(sec("05", "Who's talking", "".join(
        f'<div class="pt"><div class="pt-t">{E(p["name"])}{tag(str(p["percentage"]) + "%")}</div>'
        f'<div class="pt-d">{E(p["description"])}</div></div>' for p in d["personas"])))
    h.append(sec("06", "Next moves", "".join(
        point_html(r["title"], r["action"], [], items, badge=tag(r["priority"], r["priority"].lower()))
        for r in d["recommendations"])))
    h.append("</div>")
    st.markdown("".join(h), unsafe_allow_html=True)


def render_compare(res):
    d, items = res["data"], res["items"]
    na, nb = res["names"]
    ca, cb = res["counts"]
    n = len(items)
    lab = {"A": na, "B": nb, "Even": "Even", "Either": "Either"}
    meta = f'{E(na)} vs {E(nb)} · {E(res["industry"])} · {E(res["window"] or "your data")} · {n} items'

    def score(name, side, c):
        return (f'<div><div class="bn">{E(name)}</div>{bar(side["sentiment"])}'
                f'<div class="barkey">{c} items · confidence {conf_of(c, 40, 15)}</div></div>')

    def sw(name, side):
        s = "".join(point_html(p["title"], p["detail"], p["evidence_ids"], items) for p in side["strengths"])
        w = "".join(point_html(p["title"], p["detail"], p["evidence_ids"], items) for p in side["weaknesses"])
        return (f'<div><div class="bn">{E(name)}</div><div class="barkey">STRENGTHS</div>{s}'
                f'<div class="barkey" style="margin-top:1rem">WEAKNESSES</div>{w}</div>')

    h = [f'<div class="brief"><div class="meta">{meta}</div>',
         f'<h2 class="hl">{E(d["headline"])}</h2><div class="lede">{E(d["summary"])}</div>',
         f'<div class="cols2">{score(na, d["a"], ca)}{score(nb, d["b"], cb)}</div>']
    if min(ca, cb) < 15:
        h.append(f'<div class="warn" style="margin-top:1rem">Thin data ({E(na)}: {ca}, {E(nb)}: {cb}). '
                 'Treat the gaps below as hypotheses.</div>')
    h.append(sec("01", "Head to head", "".join(
        f'<div class="dim"><div class="pt-t">{E(x["dimension"])}</div><div class="edge">{E(lab.get(x["edge"], x["edge"]))}</div>'
        f'<div><div class="pt-d">{E(x["verdict"])}</div>{rcpts(x["evidence_ids"], items)}</div></div>'
        for x in d["dimensions"])))
    gaps = [g for g in d["gaps"] if has_evidence(g["evidence_ids"], n)]
    h.append(sec("02", "White space", "".join(
        f'<div class="gap"><div>{tag(g["kind"])}{tag("for " + lab.get(g["for_brand"], g["for_brand"]))}'
        f'{tag(g["confidence"] + " confidence", g["confidence"].lower())}</div>'
        f'<div class="hook" style="margin-top:.5rem">{E(g["gap"])}</div>'
        f'<div class="pt-d">{E(g["rationale"])}</div>'
        f'<div class="pt-d" style="margin-top:.4rem"><b>Move:</b> {E(g["move"])}</div>{rcpts(g["evidence_ids"], items)}</div>'
        for g in gaps) or '<div class="pt-d">No gap met the evidence bar. Try a longer window or more sources.</div>'))
    h.append(sec("03", "Strengths and weaknesses", f'<div class="cols2">{sw(na, d["a"])}{sw(nb, d["b"])}</div>'))
    angles = [a for a in d["angles"] if has_evidence(a["evidence_ids"], n)]
    h.append(sec("04", "Say this", "".join(
        angle_html(a, items, tag(lab[a["brand"]])) for a in angles)
        or '<div class="pt-d">No angle met the evidence bar.</div>'))
    h.append("</div>")
    st.markdown("".join(h), unsafe_allow_html=True)


def runs_for_sid(sid):
    """Runs this visitor id used in the last 24h (survives page refresh if the URL keeps ?sid=)."""
    if SB_URL and SB_KEY:
        try:
            since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
            r = requests.get(f"{SB_URL}/rest/v1/runs?select=id&session_id=eq.{sid}&created_at=gte.{since}",
                             headers=_sbh({"Prefer": "count=exact", "Range": "0-0"}), timeout=6)
            return int(r.headers["Content-Range"].split("/")[-1])
        except Exception:
            pass
    return 0


if "sid" not in st.session_state:
    sid = re.sub(r"[^a-z0-9]", "", str(st.query_params.get("sid", "")).lower())[:16] or uuid.uuid4().hex[:12]
    st.query_params["sid"] = sid
    st.session_state.sid = sid
    st.session_state.runs = runs_for_sid(sid)

# ── Masthead + shared settings ─────────────────────────────────────────────────
st.markdown(f"""<div class="mast">{APP_NAME} · customer voice → strategy brief</div>
<h1 class="hero">Turn what customers say into what to do next.</h1>
<p class="sub">Bring your own CRM reviews or survey answers, or pull public reviews for any brand. Get a sourced brief: messaging angles in customers' own words, claims to avoid, and where competitors leave the door open.</p>""",
            unsafe_allow_html=True)
quota_box = st.empty()

own_key = ""
with st.expander("🔑 Use your own free Gemini key (no usage limits)"):
    own_key = st.text_input("Gemini API key", type="password", help="Get one free at aistudio.google.com. Never stored.")
active_key = own_key.strip() or GOOGLE_KEY
capped = not own_key.strip()

s1, s2, s3 = st.columns(3)
industry = s1.selectbox("Industry", ["Electric Vehicles", "Consumer Tech", "E-Commerce", "SaaS / Software",
                                     "Retail / Fashion", "Food & Beverage", "Other"])
depth = s2.select_slider("Depth", ["Quick Scan", "Standard", "Deep Dive"], value="Standard")
window = s3.selectbox("Review window", ["Last 3 months", "Last 6 months", "Last 12 months", "All time"], index=1)
months = {"Last 3 months": 3, "Last 6 months": 6, "Last 12 months": 12, "All time": None}[window]
srcs = st.multiselect("Sources", ["YouTube", "App Store", "Hacker News"],
                      default=["YouTube", "App Store", "Hacker News"])


def caps_ok(cost=1):
    if not capped:
        return True
    if st.session_state.runs + cost > SESSION_LIMIT:
        st.warning(f"You've used all {SESSION_LIMIT} free runs. Add your own free Gemini key above to keep going.")
        return False
    if runs_today() >= DAILY_LIMIT:
        st.warning("Today's free capacity is used up. Come back tomorrow, or add your own Gemini key above.")
        return False
    return True


def source_counts(items):
    c = {}
    for it in items:
        c[it["source"]] = c.get(it["source"], 0) + 1
    return c


def find(prefix, name, hint):
    if capped:
        st.session_state.finds = st.session_state.get("finds", 0) + 1
        if st.session_state.finds > 25:
            raise RuntimeError("Lookup limit reached for this session. Add your own Gemini key above to keep going.")
    st.session_state[f"{prefix}_cands"] = find_companies(name.strip(), hint.strip(), active_key)
    st.session_state[f"{prefix}_q"] = name.strip()


def pick(prefix, label):
    cands = st.session_state.get(f"{prefix}_cands")
    if not cands:
        return None
    labels = [f"{c['name']} · {c['website']} · {c['headquarters']}" for c in cands]
    labels.append("None of these, use what I typed")
    idx = labels.index(st.radio(label, labels, key=f"{prefix}_radio"))
    if idx < len(cands):
        st.caption(cands[idx]["description"])
        return cands[idx]["name"], f"{cands[idx]['description']} ({cands[idx]['website']})"
    return st.session_state.get(f"{prefix}_q", ""), ""


def numbered(items, with_brand=None):
    lines = []
    for i, it in enumerate(items, 1):
        who = f"Brand {it['brand']}: {with_brand[it['brand']]}, " if with_brand else ""
        lines.append(f"[{i}] ({who}{it['source']}, {it.get('date') or 'n/a'}) {it['text']}")
    return "\n".join(lines)


def paste_items(text):
    parts = [p.strip() for p in re.split(r"\n+", text) if len(p.strip()) >= 15]
    parts = parts or [text.strip()[:2000]]
    return [{"source": "Pasted", "text": redact(p)[:800], "url": "", "date": ""} for p in parts[:MAX_ITEMS]]


def csv_items(df, text_col, date_col, months):
    d = df.copy()
    d[text_col] = d[text_col].astype(str)
    d = d[d[text_col].str.len() >= 15]
    dated = bool(date_col) and date_col != "(none)"
    if dated:
        d["_dt"] = pd.to_datetime(d[date_col], errors="coerce", utc=True)
        if months:
            d = d[d["_dt"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30.44 * months)]
        d = d.sort_values("_dt", ascending=False)
    out = []
    for _, r in d.head(MAX_ITEMS).iterrows():
        dt = r["_dt"] if dated else None
        out.append({"source": "CRM upload", "text": redact(r[text_col])[:800], "url": "",
                    "date": dt.strftime("%Y-%m-%d") if dt is not None and pd.notna(dt) else ""})
    return out


# ── Input tabs ─────────────────────────────────────────────────────────────────
t3, t1, t2 = st.tabs(["🏢 Analyze your own feedback", "📝 Brief on any brand", "⚔️ Compare two brands"])

with t1:
    c1, c2 = st.columns(2)
    name = c1.text_input("Brand", key="s_name", placeholder="e.g. Lucid Motors")
    hint = c2.text_input("Help me find the right one (optional)", key="s_hint", placeholder="Website or country, e.g. lucidmotors.com", help="Several companies can share a name. Add a website or country and we will show the right match.")
    if st.button("1 · Find brand", key="s_find", use_container_width=True):
        if not name.strip():
            st.warning("Type a brand name first.")
        elif caps_ok(1):
            try:
                with st.spinner("Looking for matches..."):
                    find("s", name, hint)
            except Exception as e:
                show_error(e)
    sel = pick("s", "2 · Which one did you mean?")
    if sel and st.button("3 · Write the brief", key="s_go", use_container_width=True):
        subject, desc = sel
        if not srcs:
            st.warning("Pick at least one source.")
        elif caps_ok(1):
            try:
                t0 = time.time()
                with st.spinner("Pulling reviews..."):
                    items, status = gather(subject, srcs, YT_KEY, months)
                st.caption(" · ".join(f"{k}: {v}" for k, v in status.items()))
                if len(items) < 5:
                    st.warning("Found fewer than 5 reviews in that window. Try a longer window, another source, "
                               "a more specific name, or the data tab.")
                else:
                    with st.spinner("Writing the brief..."):
                        data, model = run_analysis(
                            build_brief_prompt(industry, subject, desc, numbered(items), depth), active_key, "brief")
                    st.session_state.result = {"kind": "single", "data": data, "model": model, "industry": industry,
                                               "subject": subject, "items": items, "window": window,
                                               "source_counts": source_counts(items)}
                    st.session_state.runs += 1
                    log_run(subject, len(items), ",".join(source_counts(items)), time.time() - t0, "brief")
            except Exception as e:
                show_error(e)

with t2:
    ca, cb = st.columns(2)
    na_ = ca.text_input("Brand A", key="a_name", placeholder="e.g. Lucid Motors")
    ha_ = ca.text_input("Help me find the right one (optional)", key="a_hint", placeholder="Website or country", help="Several companies can share a name. Add a website or country and we will show the right match.")
    nb_ = cb.text_input("Brand B", key="b_name", placeholder="e.g. Rivian")
    hb_ = cb.text_input("Help me find the right one (optional)", key="b_hint", placeholder="Website or country", help="Several companies can share a name. Add a website or country and we will show the right match.")
    if st.button("1 · Find both brands", key="c_find", use_container_width=True):
        if not (na_.strip() and nb_.strip()):
            st.warning("Type both brand names first.")
        elif caps_ok(1):
            try:
                with st.spinner("Looking for matches..."):
                    find("a", na_, ha_)
                    find("b", nb_, hb_)
            except Exception as e:
                show_error(e)
    pa, pb = st.columns(2)
    with pa:
        A = pick("a", "2 · Brand A: which one?")
    with pb:
        B = pick("b", "2 · Brand B: which one?")
    if A and B and st.button("3 · Write the comparison", key="c_go", use_container_width=True):
        if not srcs:
            st.warning("Pick at least one source.")
        elif caps_ok(1):
            try:
                t0 = time.time()
                with st.spinner("Pulling reviews for both brands..."):
                    ia, sa = gather(A[0], srcs, YT_KEY, months, max_items=80)
                    ib, sb_ = gather(B[0], srcs, YT_KEY, months, max_items=80)
                st.caption(f"{A[0]}: " + " · ".join(f"{k} {v}" for k, v in sa.items())
                           + f"   |   {B[0]}: " + " · ".join(f"{k} {v}" for k, v in sb_.items()))
                if len(ia) < 5 or len(ib) < 5:
                    st.warning(f"Not enough reviews for both brands ({A[0]}: {len(ia)}, {B[0]}: {len(ib)}). "
                               "Try a longer window or more sources.")
                else:
                    for it in ia:
                        it["brand"] = "A"
                    for it in ib:
                        it["brand"] = "B"
                    items = ia + ib
                    prompt = build_compare_prompt(industry, A, B, numbered(items, {"A": A[0], "B": B[0]}),
                                                  depth, len(ia), len(ib))
                    with st.spinner("Writing the comparison..."):
                        data, model = run_analysis(prompt, active_key, "compare")
                    st.session_state.result = {"kind": "compare", "data": data, "model": model, "industry": industry,
                                               "names": (A[0], B[0]), "counts": (len(ia), len(ib)), "items": items,
                                               "window": window}
                    st.session_state.runs += 1
                    log_run(f"{A[0]} vs {B[0]}", len(items), ",".join(source_counts(items)), time.time() - t0, "compare")
            except Exception as e:
                show_error(e)

with t3:
    st.markdown('<div class="callout"><b>Built for your own data.</b> Paste or upload CRM reviews, survey answers or '
                'support tickets. Tell us what you sell so the brief reads the feedback in context. '
                'Emails and common phone formats are masked before analysis.</div>', unsafe_allow_html=True)
    o1, o2 = st.columns(2)
    own_name = o1.text_input("Your company or product", key="o_name", placeholder="e.g. Acme Smart Thermostat")
    own_url = o2.text_input("Company page link (optional)", key="o_url", placeholder="https://acme.com",
                            help="We read the page title and description so the brief knows what you sell.")
    own_desc = st.text_area("What do you sell, and to whom?", key="o_desc", height=90,
                            placeholder="e.g. A smart thermostat for renters. Buyers are mostly 25-40, in apartments, price-sensitive.")
    st.caption("Add the description, the link, or both. At least one is needed.")
    src_mode = st.radio("Your feedback", ["Paste text", "Upload CSV"], horizontal=True, key="o_mode")
    raw, df, text_col, date_col = "", None, None, None
    if src_mode == "Paste text":
        raw = st.text_area("Paste reviews, comments or survey answers (one per line)", height=200, key="p_raw")
    else:
        up = st.file_uploader("CRM or survey export (.csv, max 5 MB)", type=["csv"], key="o_csv")
        if up is not None:
            if up.size > 5_000_000:
                st.warning("That file is over 5 MB. Export a smaller date range.")
            else:
                try:
                    df = pd.read_csv(up, encoding_errors="replace")
                    df.columns = [str(c) for c in df.columns]
                except Exception as e:
                    st.error(f"Couldn't read that CSV: {e}")
                    df = None
        if df is not None and len(df.columns):
            cols = list(df.columns)
            guess = max(cols, key=lambda c: df[c].astype(str).str.len().mean())
            dguess = next((c for c in cols if any(k in c.lower() for k in ("date", "time", "created"))), "(none)")
            x1, x2 = st.columns(2)
            text_col = x1.selectbox("Which column has the feedback text?", cols, index=cols.index(guess), key="o_tcol")
            dopts = ["(none)"] + cols
            date_col = x2.selectbox("Date column (optional, enables the review window)", dopts,
                                    index=dopts.index(dguess), key="o_dcol")
            st.caption(f"{len(df):,} rows found.")
    st.caption("Heads-up: on the free Gemini tier, Google may use inputs to improve its products. "
               "Remove names and sensitive data first.")
    if st.button("Write the brief", key="p_go", use_container_width=True):
        if not own_name.strip():
            st.warning("Add your company or product name.")
        elif not (own_desc.strip() or own_url.strip()):
            st.warning("Tell us what you sell: add a short description or a link to your company page.")
        elif caps_ok(1):
            try:
                t0 = time.time()
                items, err = [], ""
                if src_mode == "Paste text":
                    if raw.strip():
                        items = paste_items(raw)
                    else:
                        err = "Paste some feedback first."
                elif df is None:
                    err = "Upload a CSV first."
                else:
                    items = csv_items(df, text_col, date_col, months)
                    if len(items) < 3:
                        err = "Fewer than 3 usable rows. Check the text column, or set Review window to All time."
                if err:
                    st.warning(err)
                else:
                    ctx = fetch_page_context(own_url.strip()) if own_url.strip() else ""
                    if own_url.strip() and not ctx:
                        st.caption("Couldn't read that page, so I'm using your description only.")
                    desc = " ".join(x for x in (own_desc.strip(), ctx) if x)[:1800]
                    with st.spinner("Writing the brief..."):
                        data, model = run_analysis(
                            build_brief_prompt(industry, own_name.strip(), desc, numbered(items), depth, own=True),
                            active_key, "brief")
                    dated = src_mode == "Upload CSV" and date_col not in (None, "(none)")
                    st.session_state.result = {"kind": "single", "data": data, "model": model, "industry": industry,
                                               "subject": own_name.strip(), "items": items,
                                               "window": window if dated else "", "source_counts": source_counts(items)}
                    st.session_state.runs += 1
                    log_run("Own data", len(items), ",".join(source_counts(items)), time.time() - t0, "own")
            except Exception as e:
                show_error(e)

# ── The brief ──────────────────────────────────────────────────────────────────
res = st.session_state.get("result")
if res:
    if res["kind"] == "compare":
        render_compare(res)
    else:
        render_single(res)
    st.caption(f"Sample of public comments and reviews, not a census. Written by {res['model']}.")
    drawer(res["items"], with_brand=res["kind"] == "compare")
    st.download_button("⬇️  Download brief data (JSON)", data=json.dumps(res["data"], indent=2, ensure_ascii=False),
                       file_name="voicebrief.json", mime="application/json", use_container_width=True)

if st.session_state.get("sb_err"):
    st.caption(f"⚠️ Usage logging failed → {st.session_state.sb_err}")

stats = sb_stats()
if stats:
    with st.expander("📈 Live usage stats"):
        a, b, c, d = st.columns(4)
        a.metric("Analyses run", f"{stats['runs']:,}")
        b.metric("Unique visitors", f"{stats['visitors']:,}")
        c.metric("Reviews analyzed", f"{stats['reviews']:,}")
        d.metric("Avg time (sec)", stats["avg_secs"])

left = max(SESSION_LIMIT - st.session_state.runs, 0)
if capped:
    quota_box.markdown(
        f'<div class="quota"><span class="dots">{"●" * left}{"○" * (SESSION_LIMIT - left)}</span>'
        f'<b>{left} of {SESSION_LIMIT}</b> free runs left <span class="qdim">· every brief or comparison = 1 run · '
        f'add your own free Gemini key for unlimited</span></div>', unsafe_allow_html=True)
else:
    quota_box.markdown('<div class="quota"><b>∞</b> Unlimited runs with your own Gemini key</div>', unsafe_allow_html=True)
