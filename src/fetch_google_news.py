"""دریافت اخبار به‌روز از Google News RSS با متادیتای کیفیت و Leader Watchlist."""
import feedparser
import requests
import time
import urllib.parse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

_FEED_TIMEOUT_SECONDS = 8
_MAX_WORKERS = 4
_MAX_RETRIES = 1
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_CIRCUIT_BREAK_AFTER = 3


def _parse_feed(url):
    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                timeout=_FEED_TIMEOUT_SECONDS,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AI-Future-Radar/1.0; +https://github.com/jamshidimoh/AI-Future-Radar)",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                    "Cache-Control": "no-cache",
                },
            )
            if response.status_code in _RETRY_STATUS_CODES:
                last_error = requests.HTTPError(f"HTTP {response.status_code}")
                if attempt < _MAX_RETRIES:
                    time.sleep(1.0 + random.uniform(0.1, 0.4))
                    continue
            response.raise_for_status()
            return feedparser.parse(response.content)
        except Exception as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                time.sleep(1.0 + random.uniform(0.1, 0.4))
    raise last_error


def _collect_query(q, cutoff):
    encoded_query = urllib.parse.quote(q["query"])
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = _parse_feed(url)
    except Exception as exc:
        return q, [], exc

    results = []
    for entry in feed.entries[:15]:
        published = entry.get("published_parsed")
        published_str = ""
        if published:
            published_ts = time.mktime(published)
            if published_ts < cutoff:
                continue
            published_str = datetime.fromtimestamp(published_ts).strftime("%Y-%m-%d %H:%M")

        title = entry.get("title", "")
        summary = entry.get("summary", "")
        link = entry.get("link", "")
        source_title = entry.get("source", {}).get("title", "Google News") if hasattr(entry, "get") else "Google News"
        watch_person = str(q.get("watch_person", "") or "").strip()
        is_leader_watch = bool(watch_person)

        results.append({
            "title": title,
            "link": link,
            "summary": summary,
            "source": f"Google News ({source_title})",
            "category": q["category"],
            "published": published_str,
            "is_trending_query": True,
            "source_tier": q.get("tier", 3),
            "source_type": "news_aggregator",
            "content_type": q.get("content_type", "news"),
            "official": False,
            "watch_person": watch_person,
            "leader": watch_person,
            "is_leader_watch": is_leader_watch,
            "leader_watch_protected": is_leader_watch,
            "_ai_link": True if is_leader_watch else None,
        })
    return q, results, None


_SERIAL_FETCH_BUDGET_SECONDS = 90


def fetch_google_news_items(queries, max_age_hours=36, max_workers=None, inter_query_delay=0.0, max_seconds=None):
    """Fetch Google News with bounded retries, a circuit breaker, and a hard time budget.

    When Google News is unavailable, fail fast rather than spending the entire
    production budget retrying dozens of identical 503 responses. Other
    discovery channels remain available and the run can complete within CI's
    execution budget.

    The consecutive-failure circuit breaker alone is not sufficient: if failures
    are interspersed with occasional successes (common under soft rate-limiting),
    the counter keeps resetting and the breaker never trips, letting a long serial
    query list (e.g. the Leader Watchlist) consume the entire CI run budget.
    A hard wall-clock budget guarantees this discovery step always terminates in
    bounded time regardless of the failure pattern.
    """
    cutoff = time.time() - (max_age_hours * 3600)
    results = []
    if not queries:
        return results
    workers = min(max_workers or _MAX_WORKERS, max(1, len(queries)))
    budget_seconds = _SERIAL_FETCH_BUDGET_SECONDS if max_seconds is None else max_seconds

    if workers == 1:
        consecutive_failures = 0
        deadline = time.monotonic() + budget_seconds
        for idx, q in enumerate(queries):
            if time.monotonic() >= deadline:
                print(
                    f"[WARN] Google News serial fetch time budget ({budget_seconds}s) exhausted "
                    f"after {idx}/{len(queries)} queries; continuing with other discovery sources.",
                    flush=True,
                )
                break
            q, items, error = _collect_query(q, cutoff)
            if error:
                consecutive_failures += 1
                query_text = str(q.get("query", ""))
                print(f"[WARN] خطا در خواندن Google News برای «{query_text}»: {error}", flush=True)
                if consecutive_failures >= _CIRCUIT_BREAK_AFTER:
                    print(f"[WARN] Google News circuit breaker opened after {consecutive_failures} consecutive failures; continuing with other discovery sources.", flush=True)
                    break
            else:
                consecutive_failures = 0
                results.extend(items)
            if inter_query_delay:
                time.sleep(inter_query_delay)
        return results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_collect_query, q, cutoff) for q in queries]
        failures = 0
        for future in as_completed(futures):
            q, items, error = future.result()
            if error:
                failures += 1
                query_text = str(q.get("query", ""))
                print(f"[WARN] خطا در خواندن Google News برای «{query_text}»: {error}", flush=True)
                continue
            results.extend(items)
    return results
