"""Synthetic QA inputs only. Never shown as a real/reference analysis."""
from copy import deepcopy


def single_result(n=24):
    items = [{"source": "Pasted", "text": f"QA source {i}: The controls are simple to use, but the setup needs clearer instructions. Café, ₹ and β are text-rendering checks.", "date": "2026-11-28", "url": ""} for i in range(1, n + 1)]
    return {"kind": "single", "origin": "own", "subject": "Quality assurance fixture", "industry": "Other", "depth": "Standard", "window": "", "created_at": "2026-11-28 10:00 UTC", "model": "QA fixture / no API call", "items": items, "data": {
        "headline": "TEST FIXTURE: useful controls, clearer setup needed", "summary": "Synthetic report used to verify layout and export. This is not a real customer analysis or the app's reference case.",
        "sentiment": {"positive": 50, "neutral": 20, "negative": 30},
        "loved": [{"title": "Clear controls", "detail": "Synthetic finding about the simplicity of the controls.", "evidence_ids": [1, 2]}],
        "pain_points": [{"title": "Setup instructions", "detail": "Synthetic users mention unclear setup.", "cause": "The feedback describes missing setup guidance.", "severity": "Medium", "evidence_ids": [2, 3]}],
        "angles": [{"hook": "Simple controls for everyday use", "why": "A test message drawn from the sample phrase.", "customer_words": "The controls are simple to use", "channel": "Landing page", "evidence_ids": [1]}],
        "avoid": [{"claim": "Effortless setup", "reason": "The synthetic source describes unclear setup.", "evidence_ids": [3]}],
        "personas": [{"name": "Setup-sensitive users", "description": "A synthetic audience hypothesis.", "percentage": 100}],
        "recommendations": [{"title": "Test clearer instructions", "action": "Review instructions with users before making a claim.", "priority": "High"}]
    }}


def comparison_result():
    result = single_result(30)
    result.update(kind="compare", origin="comparison", names=("QA Brand A", "QA Brand B"), counts=(15, 15), subject="")
    for i, item in enumerate(result["items"]):
        item.update(source="Hacker News", brand="A" if i < 15 else "B", url="https://example.com/review?id=" + str(i + 1) + "&mode=qa")
    result["data"] = {"headline": "TEST FIXTURE: a comparison of two synthetic brands", "summary": "QA data only. This is not a real comparison or a reference case.",
        "a": {"sentiment": {"positive": 55, "neutral": 20, "negative": 25}, "strengths": [{"title": "Controls", "detail": "Synthetic strength.", "evidence_ids": [1]}], "weaknesses": [{"title": "Setup", "detail": "Synthetic weakness.", "evidence_ids": [2]}]},
        "b": {"sentiment": {"positive": 45, "neutral": 25, "negative": 30}, "strengths": [{"title": "Instructions", "detail": "Synthetic strength.", "evidence_ids": [16]}], "weaknesses": [{"title": "Controls", "detail": "Synthetic weakness.", "evidence_ids": [17]}]},
        "dimensions": [{"dimension": "Ease of setup", "edge": "Even", "verdict": "Synthetic comparison; no real winner is asserted.", "evidence_ids": [1, 16]}],
        "gaps": [{"gap": "Clarity of onboarding", "kind": "Open territory", "for_brand": "Either", "rationale": "The synthetic data suggests a question worth investigating.", "move": "Test revised instructions.", "confidence": "Low", "evidence_ids": [2, 17]}],
        "angles": [{"hook": "Understand the controls", "why": "Synthetic proposal.", "customer_words": "The controls are simple to use", "channel": "Product", "brand": "A", "evidence_ids": [1]}]
    }
    return result
