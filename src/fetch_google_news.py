"""دریافت اخبار به‌روز از Google News RSS با متادیتای کیفیت و Leader Watchlist."""
import logging
import random
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import feedparser
import requests
import yaml

from src.source_authority import resolve_google_news_tier
from src.source_exclusions import is_excluded_source_text, is_excluded_source_url

logger = logging.getLogger(__name__)

_FEED_TIMEOUT_SECONDS = 8
_MAX_WORKERS = 4
_MAX_RETRIES = 1
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_CIRCUIT_BREAK_AFTER = 3
_ROOT = Path(__file__).resolve().parents[1]
_SUPPLEMENTAL_QUERY_PATH = _ROOT / "config" / "radar_google_news_queries.yaml"
_LEADER_WATCHLIST_PATH = _ROOT / "config" / "leader_watchlist.yaml"
_PIONEERS_PATH = _ROOT / "config" / "pioneers.yaml"
# Generic companion-discovery vocabulary. It deliberately avoids source-, person-,
# geography-, or platform-specific terms so the same mechanism works for every watch person.
_LEADER_SIGNAL_TERMS = (
    "statement", "says", "said", "argues", "argued", "warns", "warned", "predicts", "predicted",
    "calls for", "called for", "supports", "opposes", "criticizes", "criticised", "defends",
    "interview", "podcast", "talk", "keynote", "conversation", "discussion", "fireside",
    "transcript", "analysis", "analyses", "perspective", "opinion", "essay", "commentary",
    "forecast", "prediction", "outlook", "vision", "future", "implications", "impact",
    "research", "study", "technology", "artificial intelligence", "AI", "AGI",
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
_LEADER_ANALYTICAL_SIGNAL_TERMS = (
    "will ", "would ", "could ", "may ", "until ", "by 202", "future", "forecast", "prediction", "outlook", "timeline",
    "singularity", "existential", "consciousness", "sentience", "intimacy", "economy", "economic", "jobs", "workforce",
    "labor", "work", "society", "governance", "rules", "regulation", "risk", "safety", "business", "industry",
    "adoption", "deployment", "transformation", "impact", "implications", "reasoning", "intelligence",
)
_LEADER_SIGNAL_CONTEXT_TERMS = (
    "ai", "artificial intelligence", "agi", "machine learning", "robot", "robotics", "chip", "chips", "semiconductor",
    "compute", "computing", "data center", "datacenter", "space", "spacex", "tesla", "xai", "openai", "anthropic",
    "deepmind", "nvidia", "meta", "google", "microsoft", "apple", "amazon", "technology", "tech", "europe", "eu",
    "european", "regulation", "regulatory", "policy", "government", "law", "legislation", "governance", "safety", "risk",
    "future", "innovation", "economy", "education", "jobs", "labor", "workforce", "health", "science", "research",
    "infrastructure", "energy", "autonomy", "cybersecurity", "security", "consciousness", "singularity", "intimacy",
)
# Keep a bounded safety cap, but large enough to cover the current watchlist without
# silently dropping later people from generic companion discovery.
_MAX_LEADER_SIGNAL_QUERIES = 64


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
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, RuntimeError) as exc:
            last_error = exc
            logger.warning("Google News feed parse failed for %s: %s", url, exc, exc_info=True)
            if attempt < _MAX_RETRIES:
                time.sleep(1.0 + random.uniform(0.1, 0.4))
    raise last_error


def _load_supplemental_queries():
    if not _SUPPLEMENTAL_QUERY_PATH.exists():
        return []
    try:
        payload = yaml.safe_load(_SUPPLEMENTAL_QUERY_PATH.read_text(encoding="utf-8")) or {}
        queries = payload.get("google_news_queries", [])
        return [dict(q) for q in queries if isinstance(q, dict) and str(q.get("query") or "").strip()]
    except (OSError, UnicodeDecodeError, yaml.YAMLError, TypeError, ValueError) as exc:
        logger.warning("Supplemental Google News query registry unavailable: %s", exc, exc_info=True)
        return []


def _load_pioneer_priorities() -> dict[str, int]:
    """Load numeric expert priorities used only to order discovery queries."""
    try:
        payload = yaml.safe_load(_PIONEERS_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError, TypeError, ValueError):
        return {}
    rows = payload.get("people", []) if isinstance(payload, dict) else []
    priorities: dict[str, int] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip().casefold()
        if not name:
            continue
        try:
            priority = int(float(row.get("priority", 0) or 0))
        except (TypeError, ValueError):
            priority = 0
        priorities[name] = max(priority, priorities.get(name, 0))
    return priorities


def _query_content_type_priority(q: dict) -> int:
    ctype = str(q.get("content_type") or "").strip().casefold()
    return {
        "interview": 5,
        "podcast": 5,
        "talk": 4,
        "conversation": 4,
        "leader_signal": 3,
        "product_news": 3,
        "research": 2,
    }.get(ctype, 1)


def _is_strong_curated_query(q: dict) -> bool:
    preferred_source = str(q.get("preferred_source") or "").strip()
    query_text = str(q.get("query") or "").strip().lower()
    return bool(preferred_source or query_text.startswith("site:"))


def _load_watchlist_people_queries():
    """Generate high-recall discovery queries with equal person coverage.

    Query ordering matters because the production runner uses a bounded discovery
    window. Every watched person therefore gets a first-pass opportunity before
    lower-priority duplicate query variants consume the budget.
    """
    try:
        payload = yaml.safe_load(_LEADER_WATCHLIST_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError, TypeError, ValueError) as exc:
        logger.warning("Leader watchlist unavailable for generic discovery: %s", exc, exc_info=True)
        return []
    people = payload.get("people", {}) if isinstance(payload, dict) else {}
    rows = []
    if isinstance(people, dict):
        for group, cfg in people.items():
            if not isinstance(cfg, dict):
                continue
            group_priority = int(cfg.get("priority", 0) or 0)
            category = "mind" if str(group).strip() == "consciousness_and_mind_ai" else ("future" if "futur" in str(group).lower() else "ai")
            for raw_name in cfg.get("names", []) or []:
                name = str(raw_name).strip()
                if not name:
                    continue
                actual_priority = 0  # person identity is not a ranking signal; freshness/quality decide later
                rows.append({
                    "query": f'"{name}" ({" OR ".join(_LEADER_SIGNAL_TERMS)})',
                    "watch_person": name,
                    "category": category,
                    "tier": 1,
                    "content_type": "leader_signal",
                    "leader_discovery": True,
                    "curated_discovery": True,
                    "leader_priority": group_priority,
                    "leader_query_priority": actual_priority,
                })
    rows.sort(key=lambda q: (-_query_content_type_priority(q), str(q.get("watch_person") or "").casefold()))
    return rows

def _merge_queries(queries):
    merged = list(queries or [])
    seen = {str(q.get("query") or "").strip().lower() for q in merged if isinstance(q, dict)}
    for query in _load_supplemental_queries() + _load_watchlist_people_queries():
        key = str(query.get("query") or "").strip().lower()
        if key and key not in seen and not is_excluded_source_text(query.get("query")):
            merged.append(query)
            seen.add(key)
    # In leader mode, discovery breadth is more valuable than letting several
    # query variants for the same person crowd out other watched experts.
    leader_queries = [q for q in merged if str(q.get("watch_person") or "").strip()]
    generic_queries = [q for q in merged if not str(q.get("watch_person") or "").strip()]
    if not leader_queries:
        return merged
    buckets: dict[str, list[dict]] = {}
    for q in leader_queries:
        person = str(q.get("watch_person") or "").strip().casefold()
        buckets.setdefault(person, []).append(q)
    for bucket in buckets.values():
        bucket.sort(key=lambda q: (-_query_content_type_priority(q), str(q.get("query") or "").casefold()))
    ordered: list[dict] = []
    # First pass: one strongest query per person, maximizing person coverage.
    people = sorted(buckets)
    for person in people:
        if buckets[person]:
            ordered.append(buckets[person].pop(0))
    # Second pass: additional variants for the highest-priority people.
    remaining = [q for bucket in buckets.values() for q in bucket]
    remaining.sort(key=lambda q: (-_query_content_type_priority(q), str(q.get("watch_person") or "").casefold(), str(q.get("query") or "").casefold()))
    ordered.extend(remaining)
    return ordered + generic_queries


def _expand_leader_signal_queries(queries):
    """Bound leader discovery while guaranteeing a companion query for priority people."""
    raw = list(queries or [])
    existing = {str(q.get("query") or "").strip().lower() for q in raw}
    people: dict[str, list[dict]] = {}
    non_people: list[dict] = []
    for q in raw:
        person = str(q.get("watch_person") or "").strip()
        if person:
            people.setdefault(person.casefold(), []).append(q)
        else:
            non_people.append(q)
    signal_terms = " OR ".join(_LEADER_SIGNAL_TERMS)
    ordered_people = sorted(
        people.values(),
        key=lambda bucket: str(bucket[0].get("watch_person") or "").casefold(),
    )
    expanded: list[dict] = []
    for bucket in ordered_people:
        bucket.sort(key=lambda q: (-_query_content_type_priority(q), str(q.get("query") or "").casefold()))
        primary = bucket[0]
        expanded.append(primary)
        person = str(primary.get("watch_person") or "").strip()
        companion_query = f'"{person}" ({signal_terms})'
        companion_key = companion_query.casefold()
        if companion_key not in existing:
            companion = dict(primary)
            companion["query"] = companion_query
            companion["content_type"] = "leader_signal"
            companion["leader_discovery"] = True
            companion["curated_discovery"] = True
            expanded.append(companion)
            existing.add(companion_key)
    # Add secondary variants only after every watched person has primary+companion coverage.
    secondary = []
    for bucket in ordered_people:
        secondary.extend(bucket[1:])
    secondary.sort(key=lambda q: (-_query_content_type_priority(q), str(q.get("watch_person") or "").casefold(), str(q.get("query") or "").casefold()))
    expanded.extend(secondary)
    expanded.extend(non_people)
    return expanded[:_MAX_LEADER_SIGNAL_QUERIES]


def classify_leader_signal(title, summary, watch_person="", *, query_context="", content_type=""):
    """Classify leader results while preserving recall from an explicit watchlist query."""
    text = f"{title} {summary}".lower()
    query_text = str(query_context or "").lower()
    ctype = str(content_type or "").strip().casefold()
    interview = any(term in text for term in _LEADER_INTERVIEW_EVIDENCE_TERMS)
    activity = any(term in text for term in _LEADER_ACTIVITY_EVIDENCE_TERMS)
    analytical = any(term in text for term in _LEADER_ANALYTICAL_SIGNAL_TERMS)
    context = any(term in text for term in _LEADER_SIGNAL_CONTEXT_TERMS)
    person_signal = bool(watch_person and str(watch_person).lower() in text)
    query_person_signal = bool(watch_person and str(watch_person).lower() in query_text)
    query_context_signal = any(term in query_text for term in _LEADER_SIGNAL_CONTEXT_TERMS)
    substantive_analysis = bool(analytical and context)
    # Google News snippets frequently omit the interviewed person's name. When
    # the source came from an explicit named watchlist query, preserve the item
    # for the downstream identity/evidence/quality gates instead of deleting it
    # prematurely at discovery.
    query_format_signal = ctype in {"interview", "podcast", "talk", "conversation", "leader_signal", "product_news", "research"}
    accepted_by_watch_query = bool(
        query_person_signal
        and query_context_signal
        and (interview or activity or substantive_analysis or query_format_signal)
    )
    accepted = bool(((interview or activity or substantive_analysis) and context) or accepted_by_watch_query)
    return {
        "accepted": accepted,
        "interview": interview,
        "activity": activity,
        "analytical": analytical,
        "context": context,
        "person_signal": person_signal,
        "query_person_signal": query_person_signal,
        "query_context_signal": query_context_signal,
    }


def _has_leader_signal_evidence(title, summary):
    return classify_leader_signal(title, summary)["accepted"]


def _collect_query(q, cutoff):
    query_text = str(q.get("query", ""))
    if is_excluded_source_text(query_text):
        print(f"[Discovery Exclusion] skipped Google News query targeting excluded source: {query_text}", flush=True); return q, [], None
    encoded_query = urllib.parse.quote(query_text); url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    try: feed = _parse_feed(url)
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, RuntimeError) as exc:
        logger.warning("Google News query collection failed for %s: %s", query_text, exc, exc_info=True)
        return q, [], exc
    results = []
    for entry in feed.entries[:15]:
        published = entry.get("published_parsed"); published_str = ""
        if published:
            published_ts = time.mktime(published)
            if published_ts < cutoff: continue
            published_str = datetime.fromtimestamp(published_ts).strftime("%Y-%m-%d %H:%M")
        title = entry.get("title", ""); summary = entry.get("summary", ""); link = entry.get("link", "")
        source_obj = entry.get("source", {}) if hasattr(entry, "get") else {}
        source_title = source_obj.get("title", "Google News") if hasattr(source_obj, "get") else "Google News"
        source_href = source_obj.get("href", "") if hasattr(source_obj, "get") else ""
        if is_excluded_source_url(link) or is_excluded_source_text(source_title) or is_excluded_source_text(title): continue
        effective_tier = resolve_google_news_tier(source_title, source_href or link)
        watch_person = str(q.get("watch_person", "") or "").strip(); is_leader_watch = bool(watch_person)
        classification = classify_leader_signal(title, summary, watch_person, query_context=query_text, content_type=q.get("content_type", "news")) if q.get("leader_discovery") else None
        if q.get("leader_discovery") and not classification["accepted"]:
            print(f"[Leader Discovery Filter] dropped weak signal title={str(title)[:100]}", flush=True); continue
        results.append({"title": title, "link": link, "summary": summary, "source": f"Google News ({source_title})", "source_name": source_title, "source_domain": source_href, "category": q["category"], "published": published_str, "is_trending_query": True, "source_tier": effective_tier, "discovery_query_tier": q.get("tier", 3), "source_type": "news_aggregator", "content_type": q.get("content_type", "news"), "official": False, "preferred_source": str(q.get("preferred_source") or "").strip(), "curated_discovery": _is_strong_curated_query(q), "discovery_query": query_text, "watch_person": watch_person, "leader": watch_person, "is_leader_watch": is_leader_watch, "leader_watch_protected": is_leader_watch, "leader_signal_classification": classification, "leader_activity_signal": bool(classification and classification.get("accepted") and (classification.get("activity") or classification.get("interview") or classification.get("analytical"))), "_ai_link": True if is_leader_watch else None})
    return q, results, None

_SERIAL_FETCH_BUDGET_SECONDS = 90


def fetch_google_news_items(queries, max_age_hours=36, max_workers=None, inter_query_delay=0.0, max_seconds=None):
    cutoff = time.time() - (max_age_hours * 3600); results = []; queries = _merge_queries(queries)
    if not queries: return results
    leader_query_mode = any(str(q.get("watch_person") or "").strip() for q in queries)
    if leader_query_mode:
        original_count = len(queries); queries = _expand_leader_signal_queries(queries); added = len(queries) - original_count
        print(f"[Leader Discovery Expansion] original={original_count} expanded={len(queries)} companion={added}", flush=True)
    workers = min(max_workers or _MAX_WORKERS, max(1, len(queries)))
    if leader_query_mode and workers > 1:
        print(f"[Leader Discovery Parallel] workers={workers}", flush=True)
    budget_seconds = _SERIAL_FETCH_BUDGET_SECONDS if max_seconds is None else max_seconds
    if workers == 1:
        consecutive_failures = 0; deadline = time.monotonic() + budget_seconds
        for q in queries:
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
