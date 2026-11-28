"""Streamlit presentation of the same report content used by PDF/text exports."""
import hashlib
import html
import json
import re

import streamlit as st

from reporting import build_report_pdf, evidence_ids, limitations, public_url, report_filename, report_markdown, report_subject, sections, sentiments, source_summary


def E(value):
    return html.escape(str(value or ""))


def highlighted(text, phrase):
    if not phrase:
        return E(text)
    # Escape each fragment before adding the app-owned highlight markup.
    parts = re.split("(" + re.escape(phrase) + ")", str(text), flags=re.IGNORECASE)
    return "".join("<mark>" + E(part) + "</mark>" if part.casefold() == phrase.casefold() else E(part) for part in parts)


@st.dialog("Supporting feedback", width="large")
def show_evidence(items, ids, phrase=""):
    st.caption("Source text made available to this analysis. Review the context before using a finding.")
    for i in evidence_ids(ids, items):
        item = items[i - 1]
        brand = " / Brand " + E(item["brand"]) if item.get("brand") else ""
        st.markdown(f'<div class="evidence-block"><strong>Source {i} / {E(item.get("source", "Feedback"))}{brand}</strong><div class="sample-note">{E(item.get("date") or "Date not provided")}</div><blockquote>{highlighted(item.get("text", ""), phrase)}</blockquote></div>', unsafe_allow_html=True)
        if public_url(item.get("url")):
            st.link_button("Open original source", public_url(item["url"]))


def render_report(result):
    data, items = result["data"], result.get("items", [])
    with st.container(key="brief_report"):
        st.caption("BRAND COMPARISON" if result.get("kind") == "compare" else "YOUR STRATEGY BRIEF")
        st.markdown(f'<div class="report-title">{E(data.get("headline") or report_subject(result))}</div>', unsafe_allow_html=True)
        metadata = " / ".join(str(x) for x in (report_subject(result), result.get("industry"), result.get("window") or "Submitted feedback", f"{len(items)} feedback items") if x)
        st.markdown(f'<div class="report-meta">{E(metadata)}<br>{E(result.get("created_at", ""))}</div><div class="report-lede">{E(data.get("summary", ""))}</div>', unsafe_allow_html=True)
        counts = " / ".join(f"{name}: {amount}" for name, amount in source_summary(result).items())
        st.caption("Source coverage: " + counts)
        if result.get("kind") == "compare":
            st.caption("Brand sample sizes: " + " / ".join(f"{name}: {n}" for name, n in zip(result.get("names", []), result.get("counts", []))))
        columns = st.columns(len(sentiments(result)))
        for column, (name, values) in zip(columns, sentiments(result)):
            with column:
                st.markdown(f'<div class="sentiment-name">{E(name)}</div>', unsafe_allow_html=True)
                segments = "".join(f'<span style="width:{min(100,max(0,float(values.get(key,0))))}%;background:{color}"></span>' for key, color in zip(("positive", "neutral", "negative"), ("#5B6B4F", "#CDBF9F", "#B4472A")))
                labels = " / ".join(f"{key.title()}: {values.get(key, 0)}%" for key in ("positive", "neutral", "negative"))
                st.markdown(f'<div class="bar" aria-hidden="true">{segments}</div><div class="bar-key">{E(labels)}</div>', unsafe_allow_html=True)
        st.markdown('<p class="brief-scope">Sentiment and audience proportions are AI estimates of this sample. Sample size alone does not establish confidence or representativeness.</p>', unsafe_allow_html=True)
        for section_index, (title, entries) in enumerate(sections(result)):
            st.markdown(f'<h2 class="report-section">{E(title)}</h2>', unsafe_allow_html=True)
            if not entries:
                st.write("No supported item was returned for this section.")
            for entry_index, entry in enumerate(entries):
                st.markdown(f'<div class="finding-title">{E(entry["title"])}</div><div class="finding-detail">{E(entry["detail"])}</div>', unsafe_allow_html=True)
                if entry.get("badge"):
                    st.markdown(f'<div class="finding-badge">{E(entry["badge"])}</div>', unsafe_allow_html=True)
                if entry.get("extra"):
                    st.markdown(f'<div class="finding-extra">{E(entry["extra"])}</div>', unsafe_allow_html=True)
                if entry.get("quote"):
                    label = "Matched customer wording" if entry["quote_exact"] else "Suggested wording / not an exact source quote"
                    st.markdown(f'<div class="customer-quote-label">{E(label)}</div><div class="customer-quote">{E(entry["quote"])}</div>', unsafe_allow_html=True)
                ids = evidence_ids(entry.get("ids"), items)
                if ids and st.button("View sources " + ", ".join(str(i) for i in ids), key=f"evidence_{section_index}_{entry_index}", type="tertiary"):
                    show_evidence(items, ids, entry.get("quote", ""))
        with st.expander("Scope and limitations"):
            for note in limitations(result):
                st.write(note)
        with st.expander(f"All {len(items)} feedback items"):
            for i, item in enumerate(items, 1):
                st.markdown(f"**Source {i} / {E(item.get('source', 'Feedback'))}**")
                st.caption(str(item.get("date") or "Date not provided") + (" / Brand " + str(item["brand"]) if item.get("brand") else ""))
                st.text(item.get("text", ""))
                if public_url(item.get("url")):
                    st.link_button("Open source " + str(i), public_url(item["url"]), key=f"appendix_source_{i}")
        st.divider()
        st.markdown("### Take the brief with you")
        fingerprint = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        cached = st.session_state.get("pdf_export", {})
        if cached.get("fingerprint") != fingerprint:
            try:
                cached = {"fingerprint": fingerprint, "bytes": build_report_pdf(result)}
                st.session_state.pdf_export = cached
            except Exception:
                cached = {}
                st.error("The PDF could not be prepared. Your analysis is still available below as text and JSON; another analysis run is not needed.")
        a, b, c = st.columns([1.15, 1, 1])
        if cached.get("bytes"):
            a.download_button("Download PDF report", data=cached["bytes"], file_name=report_filename(result), mime="application/pdf", type="primary", on_click="ignore", use_container_width=True)
        text = report_markdown(result)
        b.download_button("Download text", data=text, file_name=report_filename(result, "txt"), mime="text/plain;charset=utf-8", on_click="ignore", use_container_width=True)
        c.download_button("Download JSON", data=json.dumps(data, indent=2, ensure_ascii=False), file_name=report_filename(result, "json"), mime="application/json", on_click="ignore", use_container_width=True)
        with st.expander("Copy report text"):
            st.code(text, language=None, wrap_lines=True)
        st.caption("Exports use this completed analysis. Downloading does not create a new run.")
