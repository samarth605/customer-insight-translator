import html
import ipaddress
import json
import re
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st
from pydantic import BaseModel, Field

from gemini_client import Busy, ProviderTimeout, generate_structured
from sources import gather
from report_view import render_report
from quality import AnalysisQualityError, review_analysis

APP_NAME = "VoiceBrief"
st.set_page_config(page_title=f"{APP_NAME} | customer voice to strategy brief", layout="wide")
st.markdown("<style>" + (Path(__file__).parent / "assets" / "voicebrief.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)

def secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return None


GOOGLE_KEY = secret("GOOGLE_API_KEY")
YT_KEY = secret("YOUTUBE_API_KEY")
SB_URL = (secret("SUPABASE_URL") or "").rstrip("/")
SB_KEY = secret("SUPABASE_KEY")

# Override without redeploying: add GEMINI_MODEL = "..." in Streamlit Secrets.
PRIMARY_MODEL = secret("GEMINI_MODEL") or "gemini-3.8-flash"
FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]
LOOKUP_MODEL = secret("GEMINI_LOOKUP_MODEL") or "gemini-3.5-flash-lite"
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
def _call_gemini(prompt, api_key, schema, temperature, *, lookup=False):
    models = [LOOKUP_MODEL, "gemini-3.6-flash", PRIMARY_MODEL] if lookup else [PRIMARY_MODEL, *FALLBACK_MODELS]
    return generate_structured(prompt, api_key, schema, temperature, models, lookup=lookup)


@st.cache_data(show_spinner=False, ttl=3600)
def run_analysis(prompt, api_key, kind):
    return _call_gemini(prompt, api_key, SCHEMAS[kind], 0.4)


@st.cache_data(show_spinner=False, ttl=3600)
def find_companies(name, hint, api_key):
    prompt = (f"List up to 4 distinct real companies or brands named or closely matching '{name}'"
              f"{' (hint: ' + hint + ')' if hint else ''}. Include website domain and headquarters. "
              "Only include ones you are confident exist; return fewer rather than guess.")
    data, _ = _call_gemini(prompt, api_key, Candidates, 0.1, lookup=True)
    return data["companies"]


RULES = """Rules:
- Write for a marketing lead who will act on this. Be specific and plain, no buzzwords.
- Ground every point in the numbered items. Never invent facts. Ignore items about a different company with a similar name.
- Every point, pain point, angle and avoid-item must cite 1-3 item numbers in evidence_ids.
- customer_words must be copied exactly from a cited item (under 12 words).
- Percentages: sentiment must sum to 100; personas must sum to 100.
- Ignore promotion, creator praise and unrelated comments. A public commenter is not necessarily a customer or owner.
- Distinguish the source's opinion, your interpretation and a proposed action. Do not turn comments into measured conversion, revenue or market results.
- Messaging is a hypothesis, not substantiated advertising copy. Avoid superlatives, guarantees, comparative price/performance claims and autonomous-driving or safety assurances based only on testimonials.
- A small set of opinions does not establish prevalence. Do not call a theme widespread without several relevant source items; report conflicting opinions."""


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

def source_counts(items):
    c = {}
    for it in items:
        c[it["source"]] = c.get(it["source"], 0) + 1
    return c


def find(prefix, name, hint):
    if capped:
        st.session_state.finds = st.session_state.get("finds", 0) + 1
        if st.session_state.finds > 25:
            raise RuntimeError("Lookup limit reached for this session. Add your own Gemini key in Usage & API key to keep going.")
    # Clear old matches before a request, including a failed or empty lookup.
    st.session_state[f"{prefix}_q"] = name.strip()
    st.session_state[f"{prefix}_lookup_hint"] = hint.strip()
    st.session_state[f"{prefix}_cands"] = []
    st.session_state.pop(f"{prefix}_radio", None)
    st.session_state.pop(f"{prefix}_manual", None)
    st.session_state[f"{prefix}_cands"] = find_companies(name.strip(), hint.strip(), active_key)


def same_query(prefix, name, hint):
    return (st.session_state.get(f"{prefix}_q") == name.strip()
            and st.session_state.get(f"{prefix}_lookup_hint", "") == hint.strip())


def pick(prefix, label):
    cands = st.session_state.get(f"{prefix}_cands")
    if not cands:
        name = st.session_state.get(f"{prefix}_q", "")
        if name:
            st.caption("No confident brand match is available. You can retry with a website or fuller name, or continue with the exact name you entered. Check that the collected feedback refers to the right company.")
            if st.checkbox(f"Use {name} exactly as entered", key=f"{prefix}_manual"):
                return name, ""
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



# ── Interface ─────────────────────────────────────────────────────────────────
brand, capacity, account = st.columns([2.8, 1.6, 1.2], vertical_alignment="center")
brand.markdown('<div class="wordmark">VoiceBrief<span>.</span></div>', unsafe_allow_html=True)
quota_box = capacity.empty()
with account.popover("Usage & API key", use_container_width=True):
    st.write(f"The shared service includes {SESSION_LIMIT} analyses per visitor, subject to daily capacity.")
    own_key = st.text_input("Gemini API key", type="password", key="own_api_key", help="Optional. Your key is used in this session and is not included in reports or usage logs.")
    st.caption("Your own key bypasses this app's shared-run cap. Google's quotas, availability and any billing still apply.")
    st.link_button("Get a Gemini API key", "https://aistudio.google.com/apikey")
active_key = own_key.strip() or GOOGLE_KEY
capped = not own_key.strip()

st.markdown('<h1 class="hero">From customer feedback<br>to a useful brief.</h1><p class="hero-summary">Find what customers value, the friction they describe, and messaging worth testing. Inspect the feedback behind each finding.</p>', unsafe_allow_html=True)

def task_changed():
    st.session_state.editing_inputs = True

TASKS = ["Your feedback", "Brand brief", "Compare brands"]
task = st.segmented_control("Choose your task", TASKS, default=TASKS[0], selection_mode="single", key="task_mode", on_change=task_changed) or TASKS[0]


def show_error(error, *, lookup=False):
    if isinstance(error, AnalysisQualityError):
        st.warning("The AI returned inconsistent estimates, so this analysis was not saved or counted. Your previous brief is preserved. Try again.")
    elif lookup:
        if isinstance(error, ProviderTimeout):
            st.warning("Brand matching took too long and was stopped. Try again or use the exact brand name below. No analysis run was counted.")
        elif isinstance(error, Busy):
            st.warning("Brand matching is temporarily unavailable or rate-limited. Try again shortly or use the exact brand name below. No analysis run was counted.")
        else:
            st.error("Brand matching could not be completed. Check the API key in Usage & API key, or use the exact brand name below. No analysis run was counted.")
    elif isinstance(error, ProviderTimeout):
        st.warning("The AI provider took too long and the analysis was stopped. Your previous brief is preserved and no new run was counted. Try again shortly.")
    elif isinstance(error, Busy):
        st.info("The AI provider is busy. This run was not counted. Try again shortly or use a different Gemini key in Usage & API key.")
    else:
        st.error("The analysis could not be completed. Check the API key and try again. Your previous brief is preserved and no new run was counted.")


def caps_ok(cost=1):
    if not active_key:
        st.warning("Add a Gemini API key in Usage & API key to run an analysis. This preview has no shared key configured.")
        return False
    if not capped:
        return True
    if st.session_state.runs + cost > SESSION_LIMIT:
        st.warning(f"You've used all {SESSION_LIMIT} shared runs. Use your own Gemini key in Usage & API key to continue.")
        return False
    if runs_today() >= DAILY_LIMIT:
        st.warning("Today's shared capacity is used up. Come back tomorrow, or use your own Gemini key.")
        return False
    return True


def finish(result, started, mode):
    result['data'],result['quality_checks']=review_analysis(result['data'],result['items'],result['kind'],result.get('subject') or ' and '.join(result.get('names',[])))
    result.update(created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), origin=mode)
    st.session_state.result = result
    st.session_state.runs += 1
    st.session_state.editing_inputs = False
    st.session_state.pop("pdf_export", None)
    log_run(result.get("subject") or " vs ".join(result.get("names", [])), len(result["items"]), ",".join(source_counts(result["items"])), time.time() - started, mode)
    st.rerun()


def settings():
    industry = "Other"
    with st.expander("Analysis settings", expanded=False):
        industry = st.selectbox("Industry", ["Other", "Electric Vehicles", "Consumer Tech", "E-Commerce", "SaaS / Software", "Retail / Fashion", "Food & Beverage"], key="industry")
        depth = st.select_slider("Brief depth", ["Quick Scan", "Standard", "Deep Dive"], value="Standard", key="depth")
        dated = task != "Your feedback" or st.session_state.get("o_mode") == "Upload CSV"
        window = st.selectbox("Review window", ["Last 3 months", "Last 6 months", "Last 12 months", "All time"], index=1, key="review_window") if dated else "All time"
        if task != "Your feedback":
            srcs = st.multiselect("Public sources", ["YouTube", "App Store", "Hacker News"], default=["YouTube", "App Store", "Hacker News"], key="public_sources")
            st.caption("Availability differs by source. YouTube collection requires a configured YouTube API key.")
        else:
            srcs = []
            st.caption("Only your submitted feedback is analyzed. A date window applies only when a CSV date column is selected.")
    months = {"Last 3 months": 3, "Last 6 months": 6, "Last 12 months": 12, "All time": None}[window]
    return industry, depth, window, months, srcs


def own_feedback(industry, depth, window, months):
    st.markdown('<p class="setup-intro">Bring customer reviews, survey responses or support feedback. Add enough company context to make the findings useful.</p>', unsafe_allow_html=True)
    name = st.text_input("Company or product", key="o_name", placeholder="e.g. Acme Smart Thermostat")
    description = st.text_area("What do you sell, and to whom?", key="o_desc", height=90, placeholder="A smart thermostat for renters who want simpler temperature control.")
    url = st.text_input("Company page link (optional)", key="o_url", placeholder="https://acme.com", help="We use the page title and description as company context. Add a description if the page cannot be read.")
    mode = st.radio("Feedback input", ["Paste text", "Upload CSV"], horizontal=True, key="o_mode")
    raw, df, text_col, date_col = "", None, None, None
    if mode == "Paste text":
        raw = st.text_area("Feedback, one response per line", height=170, key="p_raw")
        if raw.strip():
            st.caption(f"{len(paste_items(raw))} feedback items ready, up to {MAX_ITEMS} per brief.")
    else:
        upload = st.file_uploader("CRM or survey export (.csv, up to 5 MB)", type=["csv"], key="o_csv")
        if upload is not None:
            if upload.size > 5_000_000:
                st.warning("That file is over 5 MB. Export a smaller date range.")
            else:
                try:
                    df = pd.read_csv(upload, encoding_errors="replace")
                    df.columns = [str(c) for c in df.columns]
                except Exception:
                    st.error("This CSV could not be read. Check the file format and try again.")
        if df is not None and len(df.columns):
            columns = list(df.columns)
            guess = max(columns, key=lambda c: df[c].astype(str).str.len().mean())
            text_col = st.selectbox("Feedback text column", columns, index=columns.index(guess), key="o_tcol")
            options = ["(none)"] + columns
            guessed_date = next((c for c in columns if any(k in c.lower() for k in ("date", "time", "created"))), "(none)")
            date_col = st.selectbox("Date column (optional)", options, index=options.index(guessed_date), key="o_dcol")
            ready = csv_items(df, text_col, date_col, months)
            st.caption(f"{len(df):,} rows loaded / {len(ready):,} usable items after filtering / up to {MAX_ITEMS} analyzed.")
            st.dataframe(df[[text_col]].head(3), hide_index=True, use_container_width=True)
    st.caption("Remove sensitive information first. Common email and phone formats are masked; other identifying details can remain. Google's free API tier may use submitted content to improve its products.")
    if st.button("Write the brief", key="p_go", type="primary", use_container_width=True):
        if not name.strip(): st.warning("Add your company or product name.")
        elif not (description.strip() or url.strip()): st.warning("Add a company description, a page link, or both.")
        elif mode == "Paste text" and not raw.strip(): st.warning("Paste some feedback first.")
        elif mode == "Upload CSV" and df is None: st.warning("Upload a readable CSV first.")
        elif caps_ok():
            try:
                started = time.time()
                items = paste_items(raw) if mode == "Paste text" else csv_items(df, text_col, date_col, months)
                if len(items) < 3:
                    st.warning("Add at least 3 usable feedback items. Check the text column or choose a wider date window in Analysis settings.")
                    return
                with st.status("Preparing your brief", expanded=True) as progress:
                    st.write(f"Reading {len(items)} feedback items")
                    context = fetch_page_context(url.strip()) if url.strip() else ""
                    if url.strip() and not context and not description.strip():
                        progress.update(label="Company context needed", state="error")
                        st.warning("The company page could not be read. Add a short description and try again. No run was counted.")
                        return
                    desc = " ".join(x for x in (description.strip(), context) if x)[:1800]
                    st.write("Interpreting the feedback and writing a sourced brief")
                    data, model = run_analysis(build_brief_prompt(industry, name.strip(), desc, numbered(items), depth, own=True), active_key, "brief")
                    progress.update(label="Brief ready", state="complete", expanded=False)
                dated = mode == "Upload CSV" and date_col not in (None, "(none)")
                finish({"kind": "single", "data": data, "model": model, "industry": industry, "depth": depth, "subject": name.strip(), "items": items, "window": window if dated else "", "source_counts": source_counts(items)}, started, "own")
            except Exception as error:
                show_error(error)


def brand_brief(industry, depth, window, months, srcs):
    st.markdown('<p class="setup-intro">Choose the right company, then collect a sample of public feedback for its brief.</p>', unsafe_allow_html=True)
    name = st.text_input("Brand", key="s_name", placeholder="e.g. Lucid Motors")
    hint = st.text_input("Website or country (optional)", key="s_hint", placeholder="lucidmotors.com")
    if st.button("Find brand", key="s_find", use_container_width=True):
        if not name.strip(): st.warning("Type a brand name first.")
        elif caps_ok():
            try:
                with st.spinner("Finding matching brands..."): find("s", name, hint)
            except Exception as error: show_error(error, lookup=True)
    # A changed query must not silently analyze an older selected candidate.
    selected = pick("s", "Choose the matching brand") if same_query("s", name, hint) else None
    if selected and st.button("Write the brief", key="s_go", type="primary", use_container_width=True):
        if not srcs: st.warning("Choose at least one public source in Analysis settings.")
        elif caps_ok():
            try:
                started = time.time(); subject, desc = selected
                with st.status("Preparing your brief", expanded=True) as progress:
                    st.write("Collecting public feedback")
                    items, source_status = gather(subject, srcs, YT_KEY, months)
                    st.write("Usable source items: " + " / ".join(f"{k}: {v}" for k, v in source_status.items() if not k.startswith('_')))
                    screening=source_status.get('_quality',{})
                    if screening.get('excluded'):st.write(f"Excluded {sum(screening['excluded'].values())} recognizable promotional or off-topic items before analysis.")
                    if len(items) < 5:
                        progress.update(label="More feedback needed", state="error")
                        st.warning("Fewer than 5 usable items were found. Widen the date window, change sources or bring your own feedback. No run was counted.")
                        return
                    st.write(f"Interpreting {len(items)} feedback items and writing the brief")
                    data, model = run_analysis(build_brief_prompt(industry, subject, desc, numbered(items), depth), active_key, "brief")
                    progress.update(label="Brief ready", state="complete", expanded=False)
                finish({"kind": "single", "data": data, "model": model, "industry": industry, "depth": depth, "subject": subject, "items": items, "window": window, "source_counts": source_counts(items), "collection":source_status.get('_quality',{})}, started, "public")
            except Exception as error: show_error(error)


def compare_brands(industry, depth, window, months, srcs):
    st.markdown('<p class="setup-intro">Compare what customers value, the friction each brand faces, and positioning opportunities in the available feedback.</p>', unsafe_allow_html=True)
    a, b = st.columns(2)
    na = a.text_input("Brand A", key="a_name", placeholder="e.g. Lucid Motors")
    nb = b.text_input("Brand B", key="b_name", placeholder="e.g. Rivian")
    ha = a.text_input("Brand A website or country (optional)", key="a_hint")
    hb = b.text_input("Brand B website or country (optional)", key="b_hint")
    if st.button("Find both brands", key="c_find", use_container_width=True):
        if not (na.strip() and nb.strip()): st.warning("Type both brand names first.")
        elif caps_ok():
            try:
                # A failed lookup for one side must not prevent the other side.
                for prefix, name, hint in (("a", na, ha), ("b", nb, hb)):
                    try:
                        with st.spinner(f"Finding matches for {name.strip()}..."):
                            find(prefix, name, hint)
                    except Exception as error: show_error(error, lookup=True)
            except Exception as error: show_error(error, lookup=True)
    a, b = st.columns(2)
    with a: A = pick("a", "Choose Brand A") if same_query("a", na, ha) else None
    with b: B = pick("b", "Choose Brand B") if same_query("b", nb, hb) else None
    if A and B and st.button("Write the comparison", key="c_go", type="primary", use_container_width=True):
        if not srcs: st.warning("Choose at least one public source in Analysis settings.")
        elif A[0].casefold() == B[0].casefold(): st.warning("Choose two different brands to compare.")
        elif caps_ok():
            try:
                started = time.time()
                with st.status("Preparing your comparison", expanded=True) as progress:
                    st.write("Collecting feedback for " + A[0]); ia, sa = gather(A[0], srcs, YT_KEY, months, max_items=80)
                    st.write("Collecting feedback for " + B[0]); ib, sb = gather(B[0], srcs, YT_KEY, months, max_items=80)
                    if min(len(ia), len(ib)) < 5:
                        progress.update(label="More feedback needed", state="error")
                        st.warning(f"Both brands need at least 5 usable items ({A[0]}: {len(ia)}, {B[0]}: {len(ib)}). Widen the window or change sources. No run was counted.")
                        return
                    for item in ia: item["brand"] = "A"
                    for item in ib: item["brand"] = "B"
                    items = ia + ib
                    st.write("Comparing the evidence and writing the analysis")
                    data, model = run_analysis(build_compare_prompt(industry, A, B, numbered(items, {"A": A[0], "B": B[0]}), depth, len(ia), len(ib)), active_key, "compare")
                    progress.update(label="Comparison ready", state="complete", expanded=False)
                finish({"kind": "compare", "data": data, "model": model, "industry": industry, "depth": depth, "names": (A[0], B[0]), "counts": (len(ia), len(ib)), "items": items, "window": window, "source_counts": source_counts(items), "collection":{'A':sa.get('_quality',{}),'B':sb.get('_quality',{})}}, started, "comparison")
            except Exception as error: show_error(error)


def input_workspace():
    industry, depth, window, months, srcs = settings()
    if task == "Your feedback": own_feedback(industry, depth, window, months)
    elif task == "Brand brief": brand_brief(industry, depth, window, months, srcs)
    else: compare_brands(industry, depth, window, months, srcs)


result = st.session_state.get("result")
if result:
    with st.expander("Edit inputs or create another brief", expanded=st.session_state.get("editing_inputs", False)):
        input_workspace()
    render_report(result)
else:
    setup, preview = st.columns([1.15, 1], gap="large")
    with setup:
        input_workspace()
    with preview:
        st.markdown("""<aside class="empty-brief"><h2>A brief you<br>can inspect.</h2><p>Your completed analysis will appear here. Open a finding to read its source feedback, then export the report.</p><ul class="brief-outline"><li><strong>Customer priorities</strong><span>What people value and where they experience friction.</span></li><li><strong>Practical next steps</strong><span>Messaging to test, claims to avoid and proposed actions.</span></li><li><strong>Supporting feedback</strong><span>The source material behind each supported finding.</span></li></ul></aside>""", unsafe_allow_html=True)

reference = Path(__file__).parent / "reference_case" / "report.pdf"
if reference.is_file():
    with st.expander("Read a sample brief: Tesla"):
        st.write("Tesla, Inc. / 120 public YouTube comments / 28 November 2026")
        st.caption("Original AI-generated output from a live app run, with linked feedback and a source appendix. The sample includes off-topic and promotional comments. Some suggested claims go beyond what the cited feedback establishes; review the evidence before using the findings or messaging.")
        st.download_button("Download the Tesla sample (PDF)", data=reference.read_bytes(), file_name="voicebrief-tesla-sample.pdf", mime="application/pdf", on_click="ignore")

left = max(SESSION_LIMIT - st.session_state.runs, 0)
quota_box.markdown(f'<p class="quota-inline">{left} of {SESSION_LIMIT} shared runs available</p>' if capped else '<p class="quota-inline">Using your Gemini key</p>', unsafe_allow_html=True)
with st.expander("About this service"):
    st.caption("VoiceBrief uses Gemini to interpret a sample of feedback. Review sources and limitations before using or sharing a brief. Exporting a completed analysis does not use another run.")
    stats = sb_stats()
    if stats:
        st.caption(f"Shared service: {stats['runs']:,} analyses / {stats['reviews']:,} feedback items processed.")
