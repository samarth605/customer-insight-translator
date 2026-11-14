import html
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

import requests
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from sources import gather

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Consumer Insight Translator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg: #0D0D0D;
    --surface: #151515;
    --surface2: #1C1C1C;
    --border: #2A2A2A;
    --accent: #C8F04A;
    --accent2: #4AF0C8;
    --text: #F0F0F0;
    --muted: #888;
    --danger: #F04A4A;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
}

[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border); }

#MainMenu, footer, header { visibility: hidden; }

.hero {
    text-align: center;
    padding: 3rem 1rem 2rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}
.hero-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 1rem;
}
.hero h1 {
    font-family: 'DM Serif Display', serif;
    font-size: clamp(2.2rem, 5vw, 3.8rem);
    font-weight: 400;
    line-height: 1.1;
    color: var(--text);
    margin: 0 0 1rem;
}
.hero h1 em { color: var(--accent); font-style: italic; }
.hero p {
    color: var(--muted);
    font-size: 1rem;
    font-weight: 300;
    max-width: 540px;
    margin: 0 auto;
    line-height: 1.7;
}

.insight-block {
    background: var(--surface2);
    border-left: 3px solid var(--accent);
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}
.insight-block.pain { border-left-color: var(--danger); }
.insight-block.persona { border-left-color: var(--accent2); }
.insight-block.rec { border-left-color: #F0C84A; }
.insight-title {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.4rem;
}
.insight-body { font-size: 0.95rem; line-height: 1.65; color: var(--text); }

.pill {
    display: inline-block;
    background: #1E2A10;
    color: var(--accent);
    border: 1px solid #3A5010;
    border-radius: 100px;
    padding: 0.2rem 0.75rem;
    font-size: 0.78rem;
    font-weight: 500;
    margin: 0.2rem 0.2rem 0.2rem 0;
}

.section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.2rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border);
}
.section-header .icon {
    width: 32px; height: 32px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem;
}
.section-header h2 {
    font-family: 'DM Serif Display', serif;
    font-size: 1.3rem;
    font-weight: 400;
    margin: 0;
    color: var(--text);
}

.stTextArea textarea {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    line-height: 1.6 !important;
}
.stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(200,240,74,0.1) !important;
}

.stButton > button {
    background: var(--accent) !important;
    color: #0D0D0D !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1.8rem !important;
    transition: opacity 0.2s, transform 0.1s !important;
    letter-spacing: 0.02em !important;
}
.stButton > button:hover { opacity: 0.85 !important; transform: translateY(-1px) !important; }

.stSelectbox > div > div {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}

.divider { border: none; border-top: 1px solid var(--border); margin: 2rem 0; }

.metric-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.metric-card {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
}
.metric-number {
    font-family: 'DM Serif Display', serif;
    font-size: 2rem;
    line-height: 1;
    margin-bottom: 0.3rem;
}
.metric-label {
    font-size: 0.72rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
}

[data-baseweb="tab-list"] {
    background: var(--surface2) !important;
    border-radius: 8px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: 1px solid var(--border) !important;
}
[data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    border-radius: 6px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    background: var(--surface) !important;
    color: var(--text) !important;
}
[data-baseweb="tab-panel"] { padding-top: 1.5rem !important; }

.example-box {
    background: var(--surface2);
    border: 1px dashed var(--border);
    border-radius: 8px;
    padding: 1rem 1.2rem;
    font-size: 0.82rem;
    color: var(--muted);
    line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)

# ── Secrets & settings ─────────────────────────────────────────────────────────
def secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return None


GOOGLE_KEY = secret("GOOGLE_API_KEY")
YT_KEY = secret("YOUTUBE_API_KEY")  # optional but needed for YouTube
SB_URL = (secret("SUPABASE_URL") or "").rstrip("/")  # optional: usage logging
SB_KEY = secret("SUPABASE_KEY")
if not GOOGLE_KEY:
    st.error("GOOGLE_API_KEY missing. Add it in Streamlit Secrets.")
    st.stop()

PRIMARY_MODEL = "gemini-3.6-flash"  # stable names only; previews get retired
FALLBACK_MODEL = "gemini-2.5-flash"
MAX_CHARS = 30_000
SESSION_LIMIT = 5   # free analyses per visitor session
DAILY_LIMIT = 150   # free analyses per day across everyone

if "sid" not in st.session_state:
    st.session_state.sid = uuid.uuid4().hex[:12]
    st.session_state.runs = 0

depth_map = {
    "Quick Scan": "Provide a brief, high-level analysis with 2-3 key points per section.",
    "Standard": "Provide a balanced analysis with 3-5 points per section and moderate detail.",
    "Deep Dive": "Provide an exhaustive analysis with rich context and 5+ points per section.",
}


# ── Schemas (Gemini must return exactly these) ─────────────────────────────────
class Sentiment(BaseModel):
    positive: int
    neutral: int
    negative: int


class PainPoint(BaseModel):
    title: str
    description: str
    severity: Literal["High", "Medium", "Low"]
    evidence_ids: list[int] = Field(description="Numbers of supporting source items, max 3. Empty if none.")


class Persona(BaseModel):
    name: str
    description: str
    percentage: int


class Recommendation(BaseModel):
    title: str
    action: str
    priority: Literal["High", "Medium", "Low"]


class Insights(BaseModel):
    summary: str = Field(description="2-sentence executive summary of overall sentiment")
    sentiment: Sentiment
    themes: list[str]
    pain_points: list[PainPoint]
    personas: list[Persona]
    recommendations: list[Recommendation]
    key_quote: str = Field(description="Most representative insight, paraphrased from the data")


class Candidate(BaseModel):
    name: str
    website: str
    headquarters: str
    description: str = Field(description="One short line on what the company does")


class Candidates(BaseModel):
    companies: list[Candidate]


# ── Helpers ────────────────────────────────────────────────────────────────────
def esc(obj):
    """HTML-escape model/API text before it hits unsafe_allow_html."""
    if isinstance(obj, str):
        return html.escape(obj)
    if isinstance(obj, list):
        return [esc(i) for i in obj]
    if isinstance(obj, dict):
        return {k: esc(v) for k, v in obj.items()}
    return obj


def ev_links(ids, items):
    out = []
    for i in ids or []:
        if isinstance(i, int) and 1 <= i <= len(items) and items[i - 1]["url"].startswith("http"):
            it = items[i - 1]
            out.append(f'<a href="{html.escape(it["url"])}" target="_blank" '
                       f'style="color:var(--accent2);font-size:0.75rem;margin-right:0.8rem;">'
                       f'↗ {html.escape(it["source"])} #{i}</a>')
    return f'<div style="margin-top:0.5rem">{"".join(out)}</div>' if out else ""


def _call_gemini(prompt, api_key, schema, temperature):
    """Retry on rate limits, fall back to a second model if the first is gone."""
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=schema, temperature=temperature)
    last_err = None
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt, config=config)
                parsed = resp.parsed or schema.model_validate_json(resp.text)
                return parsed.model_dump(), model
            except Exception as e:  # noqa: BLE001
                last_err, msg = e, str(e)
                if "404" in msg or "NOT_FOUND" in msg:
                    break
                if any(c in msg for c in ("429", "503", "UNAVAILABLE")):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
    raise last_err


@st.cache_data(show_spinner=False, ttl=3600)
def run_analysis(prompt, api_key):
    return _call_gemini(prompt, api_key, Insights, 0.4)


@st.cache_data(show_spinner=False, ttl=3600)
def find_companies(name, hint, api_key):
    prompt = (f"List up to 4 distinct real companies or brands named or closely matching '{name}'"
              f"{' (hint: ' + hint + ')' if hint else ''}. Include website domain and headquarters. "
              "Only include ones you are confident exist; return fewer rather than guess.")
    data, _ = _call_gemini(prompt, api_key, Candidates, 0.1)
    return data["companies"]


def build_prompt(industry, subject, desc, body, depth, numbered):
    evidence = ("Items are numbered [n]. For each pain point, list up to 3 supporting item numbers in evidence_ids."
                if numbered else "evidence_ids may be empty.")
    return f"""You are an expert marketing strategist and consumer behavior analyst in the {industry} industry.

Subject: {subject}{' - ' + desc if desc else ''}
Analyze the consumer feedback below.

Rules:
- sentiment.positive + neutral + negative must equal 100; persona percentages must sum to 100.
- Ground every point in the data. Do not invent facts.
- Ignore items clearly about a different company or product with a similar name.
- {evidence}
- {depth_map[depth]}

Feedback:
{body}"""


# ── Usage logging + caps (Supabase is optional; falls back to in-memory) ───────
def _sbh(extra=None):
    # New-style sb_publishable_ keys are not JWTs: send on apikey only, never as Bearer.
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


# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-label">● AI-Powered Marketing Tool</div>
    <h1>Consumer Insight<br><em>Translator</em></h1>
    <p>Type a company or paste raw feedback. Get structured marketing insights from YouTube, the App Store and Hacker News in seconds.</p>
</div>
""", unsafe_allow_html=True)

# ── Main Layout ────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1.2], gap="large")

with left:
    st.markdown("""
    <div class="section-header"><div class="icon">📥</div><h2>Input</h2></div>
    """, unsafe_allow_html=True)

    own_key = ""
    with st.expander("🔑 Use your own free Gemini key (no usage limits)"):
        own_key = st.text_input("Gemini API key", type="password",
                                help="Get one free at aistudio.google.com. Never stored.")
    active_key = own_key.strip() or GOOGLE_KEY
    capped = not own_key.strip()

    c1, c2 = st.columns(2)
    industry = c1.selectbox("Industry Context", ["Electric Vehicles", "Consumer Tech", "E-Commerce",
                                                 "SaaS / Software", "Retail / Fashion", "Food & Beverage", "Other"])
    depth = c2.select_slider("Analysis Depth", ["Quick Scan", "Standard", "Deep Dive"], value="Standard")

    def caps_ok():
        if not capped:
            return True
        if st.session_state.runs >= SESSION_LIMIT:
            st.warning(f"You've used your {SESSION_LIMIT} free analyses this session. "
                       "Add your own free Gemini key above to keep going.")
            return False
        if runs_today() >= DAILY_LIMIT:
            st.warning("Today's free capacity is used up. Come back tomorrow, or add your own Gemini key above.")
            return False
        return True

    def finish(data, model, subject, items, status, secs, mode, window=""):
        counts = {}
        for it in items:
            counts[it["source"]] = counts.get(it["source"], 0) + 1
        st.session_state.result = {"data": data, "model": model, "industry": industry, "depth": depth,
                                   "subject": subject, "items": items, "source_counts": counts, "status": status, "window": window}
        st.session_state.runs += 1
        n = len(items) if items else 0
        log_run(subject, n, ",".join(counts) or "paste", secs, mode)

    tab_search, tab_paste = st.tabs(["🔎 Search by company", "📋 Paste text"])

    with tab_search:
        company = st.text_input("Company name", placeholder="e.g. Lucid Motors")
        hint = st.text_input("Website or country (optional)", placeholder="e.g. lucidmotors.com or Germany")
        window = st.selectbox("Review window", ["Last 3 months", "Last 6 months", "Last 12 months", "All time"], index=1)
        months = {"Last 3 months": 3, "Last 6 months": 6, "Last 12 months": 12, "All time": None}[window]
        if st.button("1️⃣  Find company", use_container_width=True):
            if not company.strip():
                st.warning("Type a company name first.")
            elif caps_ok():
                try:
                    with st.spinner("Looking for matches..."):
                        st.session_state.cands = find_companies(company.strip(), hint.strip(), active_key)
                        st.session_state.cand_query = company.strip()
                except Exception as e:
                    st.error(f"Something went wrong: {e}")

        cands = st.session_state.get("cands")
        if cands:
            labels = [f"{c['name']} · {c['website']} · {c['headquarters']}" for c in cands]
            labels.append("None of these, just use what I typed")
            pick = st.radio("2️⃣  Which one did you mean?", labels)
            idx = labels.index(pick)
            if idx < len(cands):
                st.caption(cands[idx]["description"])
                subject, desc = cands[idx]["name"], f"{cands[idx]['description']} ({cands[idx]['website']})"
            else:
                subject, desc = st.session_state.get("cand_query", company), ""
            srcs = st.multiselect("Sources", ["YouTube", "App Store", "Hacker News"],
                                  default=["YouTube", "App Store", "Hacker News"])
            if st.button("⚡  Pull reviews & analyze", use_container_width=True):
                if not srcs:
                    st.warning("Pick at least one source.")
                elif caps_ok():
                    try:
                        t0 = time.time()
                        with st.spinner("Pulling reviews..."):
                            items, status = gather(subject, srcs, YT_KEY, months)
                        st.caption(" · ".join(f"{k}: {v}" for k, v in status.items()))
                        if len(items) < 5:
                            st.warning("Found fewer than 5 reviews in that window. Try a longer window, another "
                                       "source, a more specific name, or the Paste tab.")
                        else:
                            body = "\n".join(f"[{i}] ({it['source']}, {it.get('date') or 'n/a'}) {it['text']}" for i, it in enumerate(items, 1))
                            prompt = build_prompt(industry, subject, desc, body, depth, True)
                            with st.spinner("Analyzing..."):
                                data, model = run_analysis(prompt, active_key)
                            finish(data, model, subject, items, status, time.time() - t0, "search", window)
                    except Exception as e:
                        st.error(f"Something went wrong: {e}")

    with tab_paste:
        data_type = st.selectbox("Data Type", ["Customer Reviews", "Social Media Comments",
                                               "Survey Responses", "Mixed / All of the above"])
        raw_data = st.text_area("Paste your raw consumer data here", height=240,
                                placeholder="Paste reviews, comments, or feedback here...")
        if st.button("⚡  Translate Insights", use_container_width=True):
            if not raw_data.strip():
                st.warning("Please paste some consumer data before analyzing.")
            elif caps_ok():
                try:
                    t0 = time.time()
                    trimmed = raw_data.strip()[:MAX_CHARS]
                    if len(raw_data.strip()) > MAX_CHARS:
                        st.warning(f"Input trimmed to the first {MAX_CHARS:,} characters.")
                    prompt = build_prompt(industry, data_type, "", trimmed, depth, False)
                    with st.spinner("Analyzing..."):
                        data, model = run_analysis(prompt, active_key)
                    finish(data, model, data_type, [], {}, time.time() - t0, "paste")
                except Exception as e:
                    st.error(f"Something went wrong: {e}")

# ── Insights panel (reads from session state so it survives reruns) ────────────
with right:
    st.markdown("""
    <div class="section-header"><div class="icon">📊</div><h2>Insights</h2></div>
    """, unsafe_allow_html=True)

    res = st.session_state.get("result")
    if not res:
        st.markdown("""
        <div style="text-align:center; padding: 4rem 2rem; color: var(--muted);">
            <div style="font-size: 2.5rem; margin-bottom: 1rem;">🔍</div>
            <p style="font-size: 1rem; margin-bottom: 0.4rem; color: #555;">Waiting for data...</p>
            <p style="font-size: 0.85rem;">Search a company or paste text on the left.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        items, model_used = res["items"], res["model"]
        industry, depth = res["industry"], res["depth"]
        data = res["data"]
        export_data = data
        data = esc(data)

# ── Results ────────────────────────────────────────────────────────────

        st.markdown(f"""
        <div style="background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: 1.2rem; margin-bottom: 1.5rem;">
            <div class="insight-title">Executive Summary</div>
            <div class="insight-body">{data.get('summary', '')}</div>
        </div>
        """, unsafe_allow_html=True)

        if data.get('key_quote'):
            st.markdown(f"""
            <div style="border-left: 3px solid var(--accent2); padding: 0.8rem 1.2rem; margin-bottom: 1.5rem; background: #0F2A24; border-radius: 0 8px 8px 0;">
                <div class="insight-title">Most Representative Voice</div>
                <div style="font-family: 'DM Serif Display', serif; font-size: 1rem; color: var(--accent2); font-style: italic; line-height: 1.6;">"{data.get('key_quote', '')}"</div>
            </div>
            """, unsafe_allow_html=True)

        sentiment = data.get('sentiment', {})
        pos = sentiment.get('positive', 0)
        neu = sentiment.get('neutral', 0)
        neg = sentiment.get('negative', 0)

        st.markdown(f"""
        <div class="metric-row">
            <div class="metric-card">
                <div class="metric-number" style="color: var(--accent);">{pos}%</div>
                <div class="metric-label">Positive</div>
            </div>
            <div class="metric-card">
                <div class="metric-number" style="color: var(--muted);">{neu}%</div>
                <div class="metric-label">Neutral</div>
            </div>
            <div class="metric-card">
                <div class="metric-number" style="color: var(--danger);">{neg}%</div>
                <div class="metric-label">Negative</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if items:
            mix = " ".join(f'<span class="pill">{html.escape(k)}: {v}</span>' for k, v in res["source_counts"].items())
            n = len(items)
            conf, col = (("High", "var(--accent)") if n >= 60 else ("Medium", "#F0C84A") if n >= 20
                         else ("Low, treat as directional", "var(--danger)"))
            st.markdown(f"""
            <div style="margin-bottom:1.2rem">
                <div class="insight-title">Based on {n} reviews{' · ' + res.get('window', '') if res.get('window') else ''} · Confidence: <span style="color:{col}">{conf}</span></div>
                {mix}
            </div>
            """, unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs(["🏷️ Themes", "🔥 Pain Points", "👤 Personas", "🎯 Recommendations"])

        with tab1:
            themes = data.get('themes', [])
            pills = " ".join([f'<span class="pill">{t}</span>' for t in themes])
            st.markdown(f"<div style='margin-bottom:1rem'>{pills}</div>", unsafe_allow_html=True)
            for t in themes:
                st.markdown(f"""
                <div class="insight-block">
                    <div class="insight-body">📌 {t}</div>
                </div>
                """, unsafe_allow_html=True)

        with tab2:
            for pp in data.get('pain_points', []):
                sev = pp.get('severity', 'Medium')
                sev_color = {'High': 'var(--danger)', 'Medium': '#F0C84A', 'Low': 'var(--muted)'}.get(sev, 'var(--muted)')
                st.markdown(f"""
                <div class="insight-block pain">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                        <div class="insight-title">{pp.get('title','')}</div>
                        <span style="font-size:0.72rem; font-weight:600; color:{sev_color}; letter-spacing:0.1em;">{sev} SEVERITY</span>
                    </div>
                    <div class="insight-body">{pp.get('description','')}</div>
                    {ev_links(pp.get('evidence_ids', []), items)}
                </div>
                """, unsafe_allow_html=True)

        with tab3:
            for p in data.get('personas', []):
                st.markdown(f"""
                <div class="insight-block persona">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                        <div class="insight-title">{p.get('name','')}</div>
                        <span style="font-size:0.85rem; font-weight:600; color:var(--accent2);">{p.get('percentage','')}% of audience</span>
                    </div>
                    <div class="insight-body">{p.get('description','')}</div>
                </div>
                """, unsafe_allow_html=True)

        with tab4:
            for r in data.get('recommendations', []):
                pri = r.get('priority', 'Medium')
                pri_color = {'High': 'var(--accent)', 'Medium': '#F0C84A', 'Low': 'var(--muted)'}.get(pri, 'var(--muted)')
                st.markdown(f"""
                <div class="insight-block rec">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                        <div class="insight-title">{r.get('title','')}</div>
                        <span style="font-size:0.72rem; font-weight:600; color:{pri_color}; letter-spacing:0.1em;">{pri} PRIORITY</span>
                    </div>
                    <div class="insight-body">→ {r.get('action','')}</div>
                </div>
                """, unsafe_allow_html=True)

        st.download_button(
            "⬇️  Download results (JSON)",
            data=json.dumps(export_data, indent=2, ensure_ascii=False),
            file_name="consumer_insights.json",
            mime="application/json",
            use_container_width=True,
        )

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align:center; color: var(--muted); font-size: 0.75rem;">
            Powered by {model_used} · {industry} · {depth} Analysis
        </div>
        """, unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem; color: #444; font-size: 0.75rem; border-top: 1px solid var(--border); margin-top: 3rem;">
    Consumer Insight Translator · Built with Streamlit + Google Gemini · CRD 494 Project
</div>
""", unsafe_allow_html=True)

stats = sb_stats()
if stats:
    with st.expander("📈 Live usage stats"):
        a, b, c, d = st.columns(4)
        a.metric("Analyses run", f"{stats['runs']:,}")
        b.metric("Unique visitors", f"{stats['visitors']:,}")
        c.metric("Reviews analyzed", f"{stats['reviews']:,}")
        d.metric("Avg time (sec)", stats["avg_secs"])

if st.session_state.get("sb_err"):
    st.caption(f"⚠️ Usage logging failed → {st.session_state.sb_err}")
