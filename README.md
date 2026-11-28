# VoiceBrief

Customer feedback interpreted as a sourced strategy brief. Built by Samarth Panchal with Python, Streamlit and the Gemini API.

## Workflows

- **Your feedback:** paste responses or upload a CSV, identify its feedback/date columns and add company context.
- **Brand brief:** confirm a company match and gather a sample of public reviews/comments.
- **Compare brands:** compare two confirmed brands with separate sample counts and shared research settings.

Public sources are YouTube, App Store and Hacker News. Availability varies. Source collection, sampling limits and masking remain as implemented in sources.py and app.py.

The opening puts the task before optional analysis settings. The paper, ink and rust visual identity is retained. Completed reports have a separate reading area, source-inspection dialogs, an appendix and exports. Changing a brand query invalidates its previous selected match.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

The review copy's Start-Preview.cmd uses port 8502. The app opens without a key for interface review. Running an analysis requires a shared server key or a personal key entered in **Usage & API key**.

For a shared deployment, add keys through Streamlit Community Cloud secrets or a local, ignored .streamlit/secrets.toml:

```toml
GOOGLE_API_KEY = "your-key"
# Optional: required for the YouTube public source
YOUTUBE_API_KEY = "your-youtube-key"
# Optional: retain existing Supabase usage logging
# SUPABASE_URL = "your-project-url"
# SUPABASE_KEY = "your-publishable-key"
# Optional: override the existing model selection
# GEMINI_MODEL = "your-enabled-model"
# Optional: fast model for the small brand-identity lookup
# GEMINI_LOOKUP_MODEL = "gemini-3.5-flash-lite"
```

Keep secrets outside version control. A visitor's personal Gemini key remains in its Streamlit session and is not included in PDF/text/JSON exports or usage logs. Personal keys bypass the app's shared-run caps; Google's quotas, model availability and any billing still apply. Existing shared limits are five analyses per visitor and 150 per day across visitors. Optional Supabase logging retains the existing schema; no database migration is needed.

## Brand matching and deadlines

Brand matching uses a fast lookup model first, with a 10-second per-request timeout and a 25-second deadline across fallback models. The SDK is limited to one attempt per model; there are no nested retries. Slow requests are cancelled. If matching is unavailable or returns no confident candidate, a visitor can explicitly choose the exact name they entered. This does not claim that the company identity was verified. Changing either the name or the hint invalidates its old matches. Comparison lookup attempts both brands independently. Analysis requests have a separate 100-second total deadline, retain the configured analysis model first, and never count a failed or timed-out analysis as a run.

## Reports and PDF export

Every completed brief or comparison offers **Download PDF report**, text and JSON downloads, plus copyable report text. Exporting uses the already-completed analysis and does not call Gemini or use another run. PDF bytes are reused within that session for the same report and invalidated when a new report completes.

The PDF contains the result, sentiment estimates, every analysis section, sample/source information, model and timestamp, limitations and the complete source text made available to the analysis. Numbered references link to the source appendix; original public URLs are clickable. Own-feedback reports are labeled as such. Quotes marked as matching use an exact, whitespace-normalized source check; unmatched wording is labeled as a suggestion.

PDFs are generated in memory with ReportLab. Noto Sans Regular and Bold are embedded under the SIL Open Font License in assets/fonts/OFL.txt. The app and text export preserve Unicode input. Symbols outside the embedded PDF font are represented by a visible Unicode codepoint and identified in a rendering note rather than silently omitted. This font covers Latin, Greek and Cyrillic; it is not a universal-script font.

Sentiment and audience-group proportions are AI estimates. Sample count is shown as sample size, not statistical confidence. Suggested priorities, causes and comparative opportunities need review and validation. Common email/phone masking does not remove every kind of identifying information. Public data is a collected sample, not a census.

## Add the genuine reference case

Run the finished app, inspect its evidence and download the chosen PDF. Save the report intended for public display as reference_case/report.pdf. The reference-case download then appears automatically. No synthetic test fixture is presented as a reference case. See reference_case/README.md.

## Tests

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests -q
```

Tests mock AI and source calls. They cover input validation, successful own/public/comparison generation, failure recovery, stale brand selections, evidence inspection, export caching, PDF content/links and long-report pagination. Synthetic QA reports are explicitly marked as test fixtures. Tests spend no analysis quota. Browser checks verify the actual downloads and responsive interface separately.

The review branch does not change the portfolio homepage or deploy the live Streamlit app. Keep app.py as the Streamlit entrypoint when this change is approved for release.

