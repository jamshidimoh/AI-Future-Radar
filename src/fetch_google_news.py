"""دریافت اخبار به‌روز از Google News RSS با متادیتای کیفیت و Leader Watchlist."""
import feedparser
import requests
import time
import urllib.parse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

try:
    from .source_exclusions import is_excluded_source_text, is_excluded_source_url
except ImportError:
    from source_exclusions import is_excluded_source_text, is_excluded_source_url

_FEED_TIMEOUT_SECONDS = 8
_MAX_WORKERS = 4
_MAX_RETRIES = 1
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_CIRCUIT_BREAK_AFTER = 3
_LEADER_SIGNAL_TERMS = (
    "statement", "says", "said", "post", "posts", "tweet", "tweets", "X post", "Twitter",
    "interview", "podcast", "talk", "keynote", "conversation", "discussion", "Europe", "EU", "European",
    "regulation", "policy", "government", "technology", "AI", "future",
)
_LEADER_INTERVIEW_EVIDENCE_TERMS = (
    "interview", "podcast", "talk", "keynote", "conversation", "discussion", "fireside", "q&a",
    "transcript", "in conversation", "speaks with", "talks with",
)
_LEADER_ACTIVITY_EVIDENCE_TERMS = (
    "statement", "say", "said", "says", "admits", "admitted", "admit", "criticiz", "criticis", "criticise", "criticize",
    "slams", "slam", "attacks", "attacked", "attack", "warn", "warns", "warned", "call for", "calls for", "called for",
    "urge", "urges", "urged", "oppose", "opposes", "opposed", "support", "supports", "supported", "back", "backs", "backed",
    "reject", "rejects", "rejected", "deny", "denies", "denied", "defend", "defends", "defended", "announce", "announced",
    "launch", "launched", "release", "released", "unveil", "unveiled", "introduce", "introduced", "acquire", "acquired",
    "acquisition", "investment", "invested", "funding", "founded", "appointed", "appoints", "joins", "partnership",
    "research project", "initiative", "product", "model", "platform", "steps down", "steps aside", "steps up",
    "reshuffle", "reorganize", "reorganise", "vision", "outlook", "forecast", "predicts", "prediction", "timeline",
)
_LEADER_SIGNAL_CONTEXT_TERMS = (
    "ai", "artificial intelligence", "agi", "machine learning", "robot", "robotics", "chip", "chips", "semiconductor",
    "compute", "computing", "data center", "datacenter", "space", "spacex", "tesla", "xai", "openai", "anthropic",
    "deepmind", "nvidia", "meta", "google", "microsoft", "apple", "amazon", "technology", "tech", "europe", "eu",
    "european", "regulation", "regulatory", "policy", "government", "law", "legislation", "governance", "safety", "risk",
    "future", "innovation", "economy", "education", "jobs", "labor", "workforce", "health", "science", "research",
    "infrastructure", "energy", "autonomy", "cybersecurity", "security",
)
_MAX_LEADER_SIGNAL_QUERIES = 24


def _parse_feed(url):
    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=_FEED_TIMEOUT_SECONDS, headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Future-Radar/1.0; +https://github.com/jamshidimoh/AI-Future-Radar)", "Accept": "application/rss+xml, application/xml, text/xml, */*", "Cache-Control": "no-cache"})
            if response.status_code in _RETRY_STATUS_CODES:
                last_error = requests.HTTPError(f"HTTP {response.status_code}")
                if attempt < _MAX_RETRIES:
                    time.sleep(1.0 + random.uniform(0.1, 0.4)); continue
            response.raise_for_status(); return feedparser.parse(response.content)
        except Exception as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                time.sleep(1.0 + random.uniform(0.1, 0.4))
    raise last_error


def _is_strong_curated_query(q: dict) -> bool:
    preferred_source = str(q.get("preferred_source") or "").strip(); query_text = str(q.get("query") or "").strip().lower()
    return bool(preferred_source or query_text.startswith("site:"))


def _expand_leader_signal_queries(queries):
    expanded = list(queries or []); existing = {str(q.get("query") or "").strip().lower() for q in expanded}; seen_people = set(); signal_terms = " OR ".join(_LEADER_SIGNAL_TERMS)
    for q in queries or []:
        person = str(q.get("watch_person") or "").strip(); person_key = person.lower()
        if not person or person_key in seen_people or len(seen_people) >= _MAX_LEADER_SIGNAL_QUERIES: continue
        seen_people.add(person_key); companion_query = f'"{person}" ({signal_terms})'; companion_key = companion_query.lower()
        if companion_key in existing: continue
        companion = dict(q); companion["query"] = companion_query; companion["content_type"] = "leader_signal"; companion["leader_discovery"] = True; companion["curated_discovery"] = True
        expanded.append(companion); existing.add(companion_key)
    return expanded


def classify_leader_signal(title, summary):
    """Classify broad Leader results by event type and technology context."""
    text = f"{title} {summary}".lower()
    interview = any(term in text for term in _LEADER_INTERVIEW_EVIDENCE_TERMS)
    activity = any(term in text for term in _LEADER_ACTIVITY_EVIDENCE_TERMS)
    context = any(term in text for term in _LEADER_SIGNAL_CONTEXT_TERMS)
    return {"accepted": bool((interview or activity) and context), "interview": interview, "activity": activity, "context": context}


def _has_leader_signal_evidence(title, summary):
    return classify_leader_signal(title, summary)["accepted"]


def _collect_query(q, cutoff):
    query_text = str(q.get("query", ""))
    if is_excluded_source_text(query_text):
        print(f"[Discovery Exclusion] skipped Google News query targeting excluded source: {query_text}", flush=True); return q, [], None
    encoded_query = urllib.parse.quote(query_text); url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    try: feed = _parse_feed(url)
    except Exception as exc: return q, [], exc
    results = []
    for entry in feed.entries[:15]:
        published = entry.get("published_parsed"); published_str = ""
        if published:
            published_ts = time.mktime(published)
            if published_ts < cutoff: continue
            published_str = datetime.fromtimestamp(published_ts).strftime("%Y-%m-%d %H:%M")
        title = entry.get("title", ""); summary = entry.get("summary", ""); link = entry.get("link", "")
        source_title = entry.get("source", {}).get("title", "Google News") if hasattr(entry, "get") else "Google News"
        if is_excluded_source_url(link) or is_excluded_source_text(source_title) or is_excluded_source_text(title): continue
        watch_person = str(q.get("watch_person", "") or "").strip(); is_leader_watch = bool(watch_person)
        classification = classify_leader_signal(title, summary) if q.get("leader_discovery") else None
        if q.get("leader_discovery") and not classification["accepted"]:
            print(f"[Leader Discovery Filter] dropped weak signal title={str(title)[:100]}", flush=True); continue
        results.append({"title": title, "link": link, "summary": summary, "source": f"Google News ({source_title})", "category": q["category"], "published": published_str, "is_trending_query": True, "source_tier": q.get("tier", 3), "source_type": "news_aggregator", "content_type": q.get("content_type", "news"), "official": False, "preferred_source": str(q.get("preferred_source") or "").strip(), "curated_discovery": _is_strong_curated_query(q), "discovery_query": query_text, "watch_person": watch_person, "leader": watch_person, "is_leader_watch": is_leader_watch, "leader_watch_protected": is_leader_watch, "leader_signal_classification": classification, "leader_activity_signal": bool(classification and classification.get("accepted") and (classification.get("activity") or classification.get("interview"))), "_ai_link": True if is_leader_watch else None})
    return q, results, None

_SERIAL_FETCH_BUDGET_SECONDS = 90


def fetch_google_news_items(queries, max_age_hours=36, max_workers=None, inter_query_delay=0.0, max_seconds=None):
    cutoff = time.time() - (max_age_hours * 3600); results = []; queries = list(queries or [])
    if not queries: return results
    leader_query_mode = any(str(q.get("watch_person") or "").strip() for q in queries)
    if leader_query_mode:
        original_count = len(queries); queries = _expand_leader_signal_queries(queries); added = len(queries) - original_count
        print(f"[Leader Discovery Expansion] original={original_count} expanded={len(queries)} companion={added}", flush=True)
    workers = min(max_workers or _MAX_WORKERS, max(1, len(queries)))
    if leader_query_mode and workers == 1 and len(queries) > 1:
        workers = min(_MAX_WORKERS, len(queries)); print(f"[Leader Discovery Parallel] workers={workers}", flush=True)
    budget_seconds = _SERIAL_FETCH_BUDGET_SECONDS if max_seconds is None else max_seconds
    if workers == 1:
        consecutive_failures = 0; deadline = time.monotonic() + budget_seconds
        for idx, q in enumerate(queries):
            if time.monotonic() >= deadline: break
            q, items, error = _collect_query(q, cutoff)
            if error:
                consecutive_failures += 1; print(f"[WARN] خطا در خواندن Google News برای «{q.get('query','') }»: {error}", flush=True)
                if consecutive_failures >= _CIRCUIT_BREAK_AFTER: break
            else:
                consecutive_failures = 0; results.extend(items)
            if inter_query_delay: time.sleep(inter_query_delay)
        return results
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_collect_query, q, cutoff) for q in queries]
        for future in as_completed(futures):
            q, items, error = future.result()
            if error: print(f"[WARN] خطا در خواندن Google News برای «{q.get('query','') }»: {error}", flush=True); continue
            results.extend(items)
    return results
