"""Shared report content and portable PDF export. No API calls or credentials."""
from __future__ import annotations

import html
import io
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from quality import collection_notes


def evidence_ids(ids, items):
    return list(dict.fromkeys(i for i in (ids or []) if type(i) is int and 1 <= i <= len(items)))


def exact_quote(phrase, ids, items):
    clean = lambda s: re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(s))).strip()
    phrase = clean(phrase)
    return bool(phrase) and any(phrase in clean(items[i - 1].get("text", "")) for i in evidence_ids(ids, items))


def public_url(value):
    value = str(value or "").strip()
    try:
        parsed = urlparse(value)
        return value if parsed.scheme in ("http", "https") and parsed.hostname else ""
    except ValueError:
        return ""


def report_subject(result):
    if result.get("kind") == "compare":
        return " vs ".join(str(x) for x in result.get("names", ["Brand A", "Brand B"]))
    return str(result.get("subject") or "Customer feedback")


def report_filename(result, extension="pdf"):
    slug = re.sub(r"[^\w-]+", "-", report_subject(result), flags=re.UNICODE).strip("-")[:75] or "analysis"
    date = str(result.get("created_at", ""))[:10]
    return f"voicebrief-{slug.lower()}{'-' + date if date else ''}.{extension}"


def source_summary(result):
    return dict(Counter(str(it.get("source") or "Feedback") for it in result.get("items", [])))


def limitations(result):
    own = result.get("origin") == "own" or all(it.get("source") in ("Pasted", "CRM upload") for it in result.get("items", []))
    notes = [
        "This brief summarizes the supplied feedback sample. It is not a census or a representative market survey.",
        "Sentiment percentages and audience-group proportions are AI estimates of this sample, not measured market shares or validated customer segments.",
        "Interpretations, possible causes and recommended actions are hypotheses to review and test; source references do not establish causation.",
    ]
    if own:
        notes.append("Source text is the submitted feedback after the app's email/phone masking and length limits. Review the report before sharing; masking does not remove every kind of personal information.")
    else:
        notes.append("Public-source availability, search relevance, date filters and item limits affect coverage. Source text may be shortened during collection.")
    if result.get("kind") == "compare":
        counts = result.get("counts", [0, 0])
        notes.append("Each brand may have different source coverage and sample sizes. A comparative edge is an interpretation of the available feedback, not proof of market leadership.")
        if min(counts or [0]) < 15:
            notes.append("At least one brand has fewer than 15 feedback items. Treat positioning opportunities as exploratory.")
    elif len(result.get("items", [])) < 20:
        notes.append("Fewer than 20 feedback items were analyzed. Treat findings as directional.")
    notes.extend(collection_notes(result.get('collection',{})))
    if result.get('quality_checks'):
        notes.append('Automated evidence and copy checks are conservative checks, not independent fact verification. Remaining interpretations and suggestions still require human review.')
    return notes


def _analysis_sections(result):
    """One content definition for the screen, text export and PDF."""
    data, items = result["data"], result.get("items", [])
    if result.get("kind") == "compare":
        names = result.get("names", ["Brand A", "Brand B"])
        labels = {"A": names[0], "B": names[1], "Even": "Even", "Either": "Either"}
        dimensions = [{"title": x["dimension"], "detail": x["verdict"], "badge": "Edge: " + str(labels.get(x["edge"], x["edge"])), "ids": x.get("evidence_ids", [])} for x in data.get("dimensions", [])]
        gaps = [{"title": g["gap"], "detail": g["rationale"], "extra": "Proposed move: " + g["move"], "badge": f"{g['kind']} / {labels.get(g['for_brand'], g['for_brand'])} / AI-assessed {g['confidence'].lower()} confidence", "ids": g.get("evidence_ids", [])} for g in data.get("gaps", []) if evidence_ids(g.get("evidence_ids"), items)]
        sides = []
        for key, name in zip(("a", "b"), names):
            for field, label in (("strengths", "Strength"), ("weaknesses", "Weakness")):
                sides.extend({"title": f"{name}: {x['title']}", "detail": x["detail"], "badge": label, "ids": x.get("evidence_ids", [])} for x in data.get(key, {}).get(field, []))
        angles = [dict(a, brand_label=labels.get(a.get("brand"), "")) for a in data.get("angles", []) if evidence_ids(a.get("evidence_ids"), items)]
        return [("Head to head", dimensions), ("Positioning opportunities", gaps), ("Strengths and weaknesses", sides), ("Messaging to test", [_angle(a, items) for a in angles])]
    return [
        ("What customers value", [{"title": x["title"], "detail": x["detail"], "ids": x.get("evidence_ids", [])} for x in data.get("loved", [])]),
        ("What's going wrong", [{"title": x["title"], "detail": x["detail"], "extra": "Possible cause: " + x["cause"], "badge": "AI-assessed severity: " + x["severity"], "ids": x.get("evidence_ids", [])} for x in data.get("pain_points", [])]),
        ("Messaging to test", [_angle(a, items) for a in data.get("angles", []) if evidence_ids(a.get("evidence_ids"), items)]),
        ("Claims to avoid", [{"title": x["claim"], "detail": x["reason"], "ids": x.get("evidence_ids", [])} for x in data.get("avoid", [])]),
        ("Audience hypotheses", [{"title": x["name"], "detail": x["description"], "badge": f"AI-estimated share of sample: {x['percentage']}%", "ids": []} for x in data.get("personas", [])]),
        ("Recommended next steps", [{"title": x["title"], "detail": x["action"], "badge": "Suggested priority: " + x["priority"], "ids": []} for x in data.get("recommendations", [])]),
    ]


def _angle(angle, items):
    return {"title": angle["hook"], "detail": angle["why"], "ids": angle.get("evidence_ids", []), "quote": angle["customer_words"], "quote_exact": exact_quote(angle["customer_words"], angle.get("evidence_ids"), items), "badge": " / ".join(x for x in (angle.get("brand_label"), angle.get("channel")) if x)}


def sections(result):
    content=_analysis_sections(result)
    checks=result.get('quality_checks',[])
    if checks:content.append(('Evidence review notes',checks))
    return content


def sentiments(result):
    if result.get("kind") == "compare":
        return [(name, result["data"][key]["sentiment"]) for key, name in zip(("a", "b"), result.get("names", ["Brand A", "Brand B"]))]
    return [("Sentiment", result["data"].get("sentiment", {}))]


def report_markdown(result):
    lines = ["# VoiceBrief", "## " + report_subject(result), "", result["data"].get("headline", ""), "", result["data"].get("summary", ""), "", f"Created: {result.get('created_at') or 'Not recorded'}", f"Industry: {result.get('industry') or 'Not specified'}", f"Brief depth: {result.get('depth') or 'Not recorded'}", f"Review window: {result.get('window') or 'Submitted feedback; no date filter'}", f"Feedback items: {len(result.get('items', []))}", "Sources: " + ", ".join(f"{k}: {v}" for k, v in source_summary(result).items()), f"Model: {result.get('model') or 'Not recorded'}", ""]
    if result.get("kind") == "compare":
        lines.append("Brand sample sizes: " + ", ".join(f"{name}: {count}" for name, count in zip(result.get("names", []), result.get("counts", []))))
    for name, values in sentiments(result):
        lines.extend([f"### {name}: AI-estimated sentiment", " | ".join(f"{label.title()}: {values.get(label, 0)}%" for label in ("positive", "neutral", "negative")), ""])
    for title, entries in sections(result):
        lines.extend(["## " + title, ""])
        if not entries:
            lines.extend(["No supported item was returned for this section.", ""])
        for entry in entries:
            lines.extend(["### " + entry["title"], entry["detail"]])
            if entry.get("badge"): lines.append(entry["badge"])
            if entry.get("extra"): lines.append(entry["extra"])
            if entry.get("quote"):
                label = "Matched customer wording" if entry["quote_exact"] else "Suggested wording (not an exact source quote)"
                lines.append(label + ": " + entry["quote"])
            ids = evidence_ids(entry.get("ids"), result.get("items", []))
            if ids: lines.append("Sources: " + ", ".join(f"[{i}]" for i in ids))
            lines.append("")
    lines.extend(["## Scope and limitations", "", *["- " + note for note in limitations(result)], "", "## Source appendix", ""])
    for i, item in enumerate(result.get("items", []), 1):
        lines.extend([f"### [{i}] {item.get('source') or 'Feedback'}" + (f" / Brand {item['brand']}" if item.get("brand") else ""), "Date: " + (item.get("date") or "Not provided"), str(item.get("text") or "")])
        if public_url(item.get("url")): lines.append(public_url(item["url"]))
        lines.append("")
    return "\n".join(str(x) for x in lines)


def build_report_pdf(result):
    """Render all analysis sections and original submitted source text in memory."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate

    font_dir = Path(__file__).parent / "assets" / "fonts"
    for name, file in (("VoiceSans", "NotoSans-Regular.ttf"), ("VoiceSansBold", "NotoSans-Bold.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_dir / file)))
    pdfmetrics.registerFontFamily("VoiceSans", normal="VoiceSans", bold="VoiceSansBold", italic="VoiceSans", boldItalic="VoiceSansBold")
    ink, rust, muted, line = map(colors.HexColor, ("#1B1B1B", "#B4472A", "#6B665C", "#D9D0BC"))
    styles = {
        "mast": ParagraphStyle("mast", fontName="VoiceSansBold", fontSize=10, leading=14, textColor=rust, spaceAfter=16),
        "title": ParagraphStyle("title", fontName="VoiceSansBold", fontSize=26, leading=32, textColor=ink, spaceAfter=15, keepWithNext=True),
        "verdict": ParagraphStyle("verdict", fontName="VoiceSansBold", fontSize=16, leading=22, textColor=ink, spaceAfter=12, keepWithNext=True),
        "body": ParagraphStyle("body", fontName="VoiceSans", fontSize=10, leading=15.5, textColor=ink, spaceAfter=9, splitLongWords=True),
        "small": ParagraphStyle("small", fontName="VoiceSans", fontSize=8.5, leading=13, textColor=muted, spaceAfter=6, splitLongWords=True),
        "section": ParagraphStyle("section", fontName="VoiceSansBold", fontSize=15, leading=20, textColor=rust, spaceBefore=23, spaceAfter=12, keepWithNext=True),
        "entry": ParagraphStyle("entry", fontName="VoiceSansBold", fontSize=11, leading=16, textColor=ink, spaceBefore=10, spaceAfter=5, keepWithNext=True),
        "quote": ParagraphStyle("quote", fontName="VoiceSans", fontSize=10, leading=15.5, leftIndent=13, borderColor=line, borderWidth=0, textColor=ink, spaceAfter=9),
        "attached": ParagraphStyle("attached", fontName="VoiceSans", fontSize=8.5, leading=13, textColor=muted, spaceAfter=6, keepWithNext=True),
    }
    # Unsupported symbols get a visible codepoint label rather than silently
    # disappearing or rendering as a false/missing glyph. Original text remains
    # available unchanged in the text/JSON export and on screen.
    available = pdfmetrics.getFont("VoiceSans").face.charToGlyph
    missing = set()
    def clean(value):
        text = unicodedata.normalize("NFC", str(value or ""))
        output = []
        for char in text:
            if char in "\n\t\r" or ord(char) in available:
                output.append(char)
            else:
                missing.add(f"U+{ord(char):04X}")
                output.append(f"[U+{ord(char):04X}]")
        return html.escape("".join(output)).replace("\n", "<br/>")
    def p(value, style="body", markup=False):
        return Paragraph(str(value) if markup else clean(value), styles[style])
    stream = io.BytesIO()
    width, height = A4
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=48, leftMargin=48, topMargin=56, bottomMargin=53, title="VoiceBrief - " + report_subject(result), author="VoiceBrief", subject="Customer feedback analysis with source appendix")
    story = [p("VOICEBRIEF / CUSTOMER RESEARCH", "mast"), p(report_subject(result), "title"), p(result["data"].get("headline", ""), "verdict"), p(result["data"].get("summary", ""))]
    for label, value in [("Analysis", "Brand comparison" if result.get("kind") == "compare" else "Own feedback" if result.get("origin") == "own" else "Brand brief"), ("Created", result.get("created_at") or "Not recorded"), ("Industry", result.get("industry") or "Not specified"), ("Brief depth", result.get("depth") or "Not recorded"), ("Review window", result.get("window") or "Submitted feedback; no date filter"), ("Feedback items", len(result.get("items", []))), ("Sources", ", ".join(f"{k}: {v}" for k, v in source_summary(result).items())), ("Model", result.get("model") or "Not recorded")]:
        story.append(p(f"{label}: {value}", "small"))
    if result.get("kind") == "compare":
        story.append(p("Brand sample sizes: " + ", ".join(f"{name}: {count}" for name, count in zip(result.get("names", []), result.get("counts", []))), "small"))

    class SentimentBar(Flowable):
        def __init__(self, values):
            super().__init__(); self.values = values; self.width = width - 96; self.height = 17
        def draw(self):
            palette = ("#5B6B4F", "#CDBF9F", "#B4472A")
            self.canv.setFillColor(line); self.canv.rect(0, 5, self.width, 8, fill=1, stroke=0)
            cursor = 0
            for key, color in zip(("positive", "neutral", "negative"), palette):
                amount = min(max(float(self.values.get(key, 0)), 0), 100) / 100 * self.width
                amount = min(amount, self.width - cursor)
                self.canv.setFillColor(colors.HexColor(color)); self.canv.rect(cursor, 5, max(0, amount), 8, fill=1, stroke=0); cursor += amount
    for name, values in sentiments(result):
        story.extend([p(str(name) + " / AI-estimated sentiment", "entry"), SentimentBar(values), p(" | ".join(f"{key.title()}: {values.get(key, 0)}%" for key in ("positive", "neutral", "negative")), "small")])
    for title, entries in sections(result):
        story.append(p(title, "section"))
        if not entries: story.append(p("No supported item was returned for this section."))
        for entry in entries:
            group = [p(entry["title"], "entry"), p(entry["detail"])]
            for key in ("badge", "extra"):
                if entry.get(key): group.append(p(entry[key], "small" if key == "badge" else "body"))
            if entry.get("quote"):
                label = "Matched customer wording" if entry["quote_exact"] else "Suggested wording (not an exact source quote)"
                group.extend([p(label, "attached"), p(entry["quote"], "quote")])
            ids = evidence_ids(entry.get("ids"), result.get("items", []))
            if ids:
                links = "Sources: " + "  ".join(f'<link href="#source-{i}" color="#B4472A">[{i}]</link>' for i in ids)
                group.append(p(links, "small", markup=True))
            story.append(KeepTogether(group))
    story.append(p("Scope and limitations", "section"))
    story.extend(p(note, "small") for note in limitations(result))
    story.append(PageBreak())
    story.append(p("Source appendix", "section"))
    story.append(p("References link to the numbered feedback below. This is the source text made available to the analysis, including any collection limits or masking.", "attached"))
    for i, item in enumerate(result.get("items", []), 1):
        title = f"[{i}] {item.get('source') or 'Feedback'}" + (f" / Brand {item['brand']}" if item.get("brand") else "")
        group = [p(f'<a name="source-{i}"/>{clean(title)}', "entry", markup=True), p("Date: " + (item.get("date") or "Not provided"), "attached"), p(item.get("text", ""), "quote")]
        url = public_url(item.get("url"))
        if url:
            group.append(p(f'<link href="{html.escape(url, quote=True)}" color="#B4472A">{clean(url)}</link>', "small", markup=True))
        story.append(KeepTogether(group))
    # Run clean() above before deciding whether the report needs this note.
    if missing:
        story.extend([p("Text rendering note", "section"), p("Symbols outside the embedded font are represented by their Unicode codepoint (for example [U+1F642]). The source text is preserved in the text export. Affected symbols: " + ", ".join(sorted(missing)), "small")])
    def page_chrome(canvas, _doc):
        canvas.saveState(); canvas.setStrokeColor(line); canvas.line(48, height - 35, width - 48, height - 35)
        canvas.setFont("VoiceSans", 8); canvas.setFillColor(muted); canvas.drawString(48, 30, "VoiceBrief / AI-assisted analysis / Review before use")
        canvas.drawRightString(width - 48, 30, f"Page {_doc.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=page_chrome, onLaterPages=page_chrome)
    return stream.getvalue()
