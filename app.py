import streamlit as st
from google import genai
import json

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

# ── Load API key from Streamlit Secrets ────────────────────────────────────────
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    client = genai.Client(api_key=api_key)
except Exception:
    st.error("API key not configured. Please add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-label">● AI-Powered Marketing Tool</div>
    <h1>Consumer Insight<br><em>Translator</em></h1>
    <p>Paste raw consumer data — reviews, comments, feedback — and get structured marketing insights in seconds.</p>
</div>
""", unsafe_allow_html=True)

# ── Main Layout ────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1.2], gap="large")

with left:
    st.markdown("""
    <div class="section-header">
        <div class="icon">📥</div>
        <h2>Input Data</h2>
    </div>
    """, unsafe_allow_html=True)

    industry = st.selectbox(
        "Industry Context",
        ["Electric Vehicles", "Consumer Tech", "E-Commerce", "SaaS / Software", "Retail / Fashion", "Food & Beverage", "Other"],
    )

    data_type = st.selectbox(
        "Data Type",
        ["Customer Reviews", "Social Media Comments", "Survey Responses", "Mixed / All of the above"],
    )

    raw_data = st.text_area(
        "Paste your raw consumer data here",
        height=280,
        placeholder="Paste reviews, comments, or feedback here...\n\nExample:\n'The range anxiety is real. I love the car but charging infrastructure is too sparse...'\n'Customer service took 3 weeks to respond. Unacceptable for a $70k vehicle.'\n'Best driving experience I've ever had. Worth every penny.'"
    )

    depth = st.select_slider(
        "Analysis Depth",
        options=["Quick Scan", "Standard", "Deep Dive"],
        value="Standard"
    )

    st.markdown("<br>", unsafe_allow_html=True)
    analyze = st.button("⚡  Translate Insights", use_container_width=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("""
    <div class="example-box">
        <strong style="color: #666;">💡 What you'll get:</strong><br>
        Key themes · Pain point heatmap · Behavioral personas · Sentiment breakdown · Actionable marketing recommendations
    </div>
    """, unsafe_allow_html=True)

# ── Analysis ───────────────────────────────────────────────────────────────────
with right:
    st.markdown("""
    <div class="section-header">
        <div class="icon">📊</div>
        <h2>Insights</h2>
    </div>
    """, unsafe_allow_html=True)

    if not analyze:
        st.markdown("""
        <div style="text-align:center; padding: 4rem 2rem; color: var(--muted);">
            <div style="font-size: 2.5rem; margin-bottom: 1rem;">🔍</div>
            <p style="font-size: 1rem; margin-bottom: 0.4rem; color: #555;">Waiting for data...</p>
            <p style="font-size: 0.85rem;">Paste your consumer data on the left and hit <strong style="color:var(--accent)">Translate Insights</strong></p>
        </div>
        """, unsafe_allow_html=True)

    elif not raw_data.strip():
        st.warning("Please paste some consumer data before analyzing.")

    else:
        depth_map = {
            "Quick Scan": "Provide a brief, high-level analysis with 2-3 key points per section.",
            "Standard": "Provide a balanced analysis with 3-5 points per section and moderate detail.",
            "Deep Dive": "Provide an exhaustive analysis with rich context and 5+ points per section."
        }

        prompt = f"""You are an expert marketing strategist and consumer behavior analyst specializing in the {industry} industry.

Analyze the following {data_type} and return ONLY a valid JSON object. No markdown, no backticks, no explanation — raw JSON only.

Use this exact structure:
{{
  "summary": "2-sentence executive summary of overall consumer sentiment",
  "sentiment": {{
    "positive": 65,
    "neutral": 15,
    "negative": 20
  }},
  "themes": ["Theme 1", "Theme 2", "Theme 3", "Theme 4", "Theme 5"],
  "pain_points": [
    {{"title": "Pain Point Name", "description": "What it is and why it matters", "severity": "High"}},
    {{"title": "Pain Point Name", "description": "What it is and why it matters", "severity": "Medium"}}
  ],
  "personas": [
    {{"name": "Persona Name", "description": "Behavioral description and motivations", "percentage": 40}},
    {{"name": "Persona Name", "description": "Behavioral description and motivations", "percentage": 35}}
  ],
  "recommendations": [
    {{"title": "Recommendation Title", "action": "Specific actionable marketing recommendation", "priority": "High"}},
    {{"title": "Recommendation Title", "action": "Specific actionable marketing recommendation", "priority": "Medium"}},
    {{"title": "Recommendation Title", "action": "Specific actionable marketing recommendation", "priority": "Low"}}
  ],
  "key_quote": "The single most representative insight paraphrased from the data"
}}

{depth_map[depth]}

Raw consumer data:
{raw_data}"""

        with st.spinner("Analyzing consumer data..."):
            try:
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=prompt
                )
                raw_json = response.text.strip()

                if raw_json.startswith("```"):
                    raw_json = raw_json.split("```")[1]
                    if raw_json.startswith("json"):
                        raw_json = raw_json[4:]
                    raw_json = raw_json.strip()

                data = json.loads(raw_json)

            except json.JSONDecodeError:
                st.error("The AI returned an unexpected format. Please try again.")
                st.stop()
            except Exception as e:
                st.error(f"Something went wrong: {str(e)}")
                st.stop()

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

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align:center; color: var(--muted); font-size: 0.75rem;">
            Powered by Gemini 3 Flash · {industry} · {depth} Analysis
        </div>
        """, unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem; color: #444; font-size: 0.75rem; border-top: 1px solid var(--border); margin-top: 3rem;">
    Consumer Insight Translator · Built with Streamlit + Google Gemini · CRD 494 Project
</div>
""", unsafe_allow_html=True)
