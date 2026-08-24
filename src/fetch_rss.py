"""دریافت اخبار به‌روز از RSS با taxonomy سخت‌گیرانه و متادیتای کیفیت منبع."""
import re
import feedparser
import requests
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    from .source_exclusions import is_excluded_source_url
except ImportError:
    from source_exclusions import is_excluded_source_url

_WEAK_AI_KEYWORDS = {"ai"}
_FEED_TIMEOUT_SECONDS = 20
_MAX_WORKERS = 6
_ROOT = Path(__file__).resolve().parents[1]
_SUPPLEMENTAL_SOURCES_PATHS = (
    _ROOT / "config" / "anthropic_rss_sources.yaml",
    _ROOT / "config" / "radar_rss_sources.yaml",
)


def _keyword_match(text, keyword):
    keyword = str(keyword or "").strip().lower()
    if not keyword or keyword in _WEAK_AI_KEYWORDS:
        return False
    if len(keyword) <= 5 and re.fullmatch(r"[a-z0-9]+", keyword):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text))
    return keyword in text


def _parse_feed(url):
    try:
        response = requests.get(
            url,
            timeout=_FEED_TIMEOUT_SECONDS,
            headers={"User-Agent": "AI-Future-Radar/1.0"},
        )
        response.raise_for_status()
        return feedparser.parse(response.content)
    except requests.RequestException as exc:
        raise RuntimeError(f"feed request failed: {exc}") from exc


def _load_supplemental_sources():
    """Load optional source extensions without changing the canonical source policy."""
    merged = []
    for path in _SUPPLEMENTAL_SOURCES_PATHS:
        if not path.exists():
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            sources = payload.get("rss_sources", [])
            if isinstance(sources, list):
                merged.extend(source for source in sources if isinstance(source, dict))
        except Exception as exc:
            print(f"[WARN] supplemental RSS registry unavailable: {path.name}: {exc}", flush=True)
    return merged


def _merge_rss_sources(rss_sources):
    merged = []
    seen = set()
    for source in list(rss_sources or []) + _load_supplemental_sources():
        if not isinstance(source, dict):
            continue
        url = str(source.get("url", "")).rstrip("/")
        if not url or url in seen:
            continue
        if is_excluded_source_url(url) or is_excluded_source_url(source.get("name")):
            print(f"[Discovery Exclusion] skipped RSS source: {source.get('name', url)}", flush=True)
            continue
        merged.append(source)
        seen.add(url)
    return merged


def _collect_source(source, categories, cutoff):
    if is_excluded_source_url(source.get("url")) or is_excluded_source_url(source.get("name")):
        return source, [], None
    try:
        feed = _parse_feed(source["url"])
    except Exception as exc:
        return source, [], exc

    results = []
    source_name = source["name"]
    source_category = str(source.get("mission") or "").strip().lower() or None

    for entry in feed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        published_str = ""
        if published:
            published_ts = time.mktime(published)
            if published_ts < cutoff:
                continue
            published_str = datetime.fromtimestamp(published_ts).strftime("%Y-%m-%d %H:%M")

        title = entry.get("title", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        link = entry.get("link", "")
        if is_excluded_source_url(link):
            continue
        text_to_check = f"{title} {summary}".lower()

        matched_category = source_category
        if matched_category is None:
            for cat_key, cat_info in categories.items():
                if any(_keyword_match(text_to_check, kw) for kw in cat_info.get("keywords", [])):
                    matched_category = cat_key
                    break

        if matched_category:
            results.append({
                "title": title,
                "link": link,
                "summary": summary,
                "source": source_name,
                "category": matched_category,
                "published": published_str,
                "source_tier": source.get("tier", 3),
                "source_type": source.get("type", "news"),
                "content_type": source.get("content_type", "research"),
                "official": bool(source.get("official", False)),
                "mission_source": str(source.get("mission") or matched_category),
            })
    return source, results, None


def fetch_rss_items(rss_sources, categories, max_age_hours=48):
    rss_sources = _merge_rss_sources(rss_sources)
    cutoff = time.time() - (max_age_hours * 3600)
    results = []
    workers = min(_MAX_WORKERS, max(1, len(rss_sources)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_collect_source, source, categories, cutoff) for source in rss_sources]
        for future in as_completed(futures):
            source, items, error = future.result()
            if error:
                print(f"[WARN] خطا در خواندن {source['name']}: {error}", flush=True)
                continue
            results.extend(items)
    print(f"[RSS Discovery] configured={len(rss_sources)} accepted={len(results)}", flush=True)
    return results
