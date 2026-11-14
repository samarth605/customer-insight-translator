"""Free review fetchers. Each returns a list of {source, text, url} dicts."""
import html
import re
from datetime import datetime, timedelta, timezone
from itertools import zip_longest

import requests

TIMEOUT = 12
UA = {"User-Agent": "ConsumerInsightTranslator/1.0 (student project)"}
ALL_SOURCES = ["YouTube", "App Store", "Hacker News"]


def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def _parse(ts):
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _fresh(date, cutoff):
    """Keep an item if there's no cutoff, or it has a date on/after the cutoff."""
    return cutoff is None or (date is not None and date >= cutoff)


def fetch_youtube(company, key, cutoff=None, max_videos=5, per_video=40):
    if not key:
        raise RuntimeError("no YOUTUBE_API_KEY set")
    base = "https://www.googleapis.com/youtube/v3"
    r = requests.get(f"{base}/search", timeout=TIMEOUT, params={
        "part": "snippet", "q": f"{company} review", "type": "video",
        "maxResults": max_videos, "relevanceLanguage": "en", "key": key,
        **({"publishedAfter": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")} if cutoff else {})})
    r.raise_for_status()
    items = []
    for v in r.json().get("items", []):
        vid = v["id"]["videoId"]
        cr = requests.get(f"{base}/commentThreads", timeout=TIMEOUT, params={
            "part": "snippet", "videoId": vid, "maxResults": per_video,
            "order": "relevance", "textFormat": "plainText", "key": key})
        if cr.status_code != 200:  # comments disabled on that video
            continue
        for c in cr.json().get("items", []):
            top = c["snippet"]["topLevelComment"]
            text = _clean(top["snippet"]["textDisplay"])
            date = _parse(top["snippet"].get("publishedAt", ""))
            if len(text) >= 40 and _fresh(date, cutoff):
                items.append({"source": "YouTube", "text": text, "date": date.strftime("%Y-%m-%d"),
                              "url": f"https://www.youtube.com/watch?v={vid}&lc={top['id']}"})
    return items


def fetch_appstore(company, cutoff=None, country="us"):
    r = requests.get("https://itunes.apple.com/search", timeout=TIMEOUT, headers=UA,
                     params={"term": company, "entity": "software", "limit": 5, "country": country})
    r.raise_for_status()
    first = company.lower().split()[0]
    apps = [a for a in r.json().get("results", [])
            if first in f"{a.get('trackName', '')} {a.get('sellerName', '')}".lower()][:2]
    items = []
    for a in apps:
        for page in (1, 2, 3, 4):
            u = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
                 f"page={page}/id={a['trackId']}/sortby=mostrecent/json")
            rr = requests.get(u, timeout=TIMEOUT, headers=UA)
            if rr.status_code != 200:
                break
            entries = rr.json().get("feed", {}).get("entry", [])
            if isinstance(entries, dict):
                entries = [entries]
            for e in entries:
                if "im:rating" not in e:  # first entry is app metadata
                    continue
                text = _clean(f"{e['title']['label']}. {e['content']['label']}")
                date = _parse(e.get("updated", {}).get("label", ""))
                if not _fresh(date, cutoff):
                    continue
                items.append({"source": "App Store", "date": date.strftime("%Y-%m-%d") if date else "",
                              "text": f"({e['im:rating']['label']}/5 stars) {text}",
                              "url": a.get("trackViewUrl", "https://apps.apple.com")})
    return items


def fetch_hn(company, cutoff=None, limit=40):
    r = requests.get("https://hn.algolia.com/api/v1/search", timeout=TIMEOUT, headers=UA,
                     params={"query": f'"{company}"', "tags": "comment", "hitsPerPage": limit,
                             **({"numericFilters": f"created_at_i>{int(cutoff.timestamp())}"} if cutoff else {})})
    r.raise_for_status()
    items = []
    for h in r.json().get("hits", []):
        text = _clean(h.get("comment_text"))
        if len(text) >= 60 and company.lower() in text.lower():
            items.append({"source": "Hacker News", "text": text,
                          "date": (h.get("created_at") or "")[:10],
                          "url": f"https://news.ycombinator.com/item?id={h['objectID']}"})
    return items


def gather(company, sources, yt_key, months=6, max_items=120, item_chars=400):
    """Run chosen fetchers, dedupe, interleave so no source dominates.
    Returns (items, status) where status maps source -> count or error note."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30.44 * months) if months else None
    fetchers = {
        "YouTube": lambda: fetch_youtube(company, yt_key, cutoff),
        "App Store": lambda: fetch_appstore(company, cutoff),
        "Hacker News": lambda: fetch_hn(company, cutoff),
    }
    by_source, status = {}, {}
    for s in sources:
        try:
            by_source[s] = fetchers[s]()
            status[s] = len(by_source[s])
        except Exception as e:  # one dead source must not kill the run
            by_source[s], status[s] = [], f"failed ({str(e)[:60]})"
    seen, merged = set(), []
    for group in zip_longest(*by_source.values()):
        for it in group:
            if not it:
                continue
            key = it["text"][:80].lower()
            if key in seen:
                continue
            seen.add(key)
            it["text"] = it["text"][:item_chars]
            merged.append(it)
            if len(merged) >= max_items:
                return merged, status
    return merged, status
