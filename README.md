# Consumer Insight Translator
### CRD 494 — AI-Powered Marketing Tool | Samarth R Panchal

Converts raw consumer data (reviews, comments, feedback) into structured marketing insights using Claude AI.

---

## What it does

- Identifies key themes from unstructured consumer data
- Maps pain points with severity ratings
- Generates behavioral customer personas
- Provides prioritized marketing recommendations
- Sentiment breakdown (positive / neutral / negative)

---

## Deploy on Streamlit Cloud (Free)

1. Fork or upload this repo to your GitHub account
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select your repo → set `app.py` as the main file
4. Under **Advanced settings → Secrets**, add:
   ```
   ANTHROPIC_API_KEY = "sk-ant-your-key-here"
   ```
5. Click **Deploy** — you'll get a public link in ~2 minutes

---

## Get your free Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up (free)
3. Go to **API Keys** → Create new key
4. Paste it into Streamlit secrets (step 4 above)

---

## Run locally

```bash
pip install streamlit anthropic
streamlit run app.py
```

---

## AI Tools Used

| Tool | Role |
|------|------|
| Claude Sonnet (Anthropic API) | Core insight generation engine |
| Streamlit | Web app framework |
| ChatGPT | Project ideation and proposal structuring (documented in assignment) |
| Gemini (Thinking) | System workflow design (documented in assignment) |

---

## Tech Stack

- Python 3.10+
- Streamlit 1.35+
- Anthropic Python SDK
- Claude Sonnet 4
