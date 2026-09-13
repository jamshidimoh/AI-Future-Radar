"""Production launcher with canonical period ranking and audit."""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import period_ranked_pipeline as pipeline
from src.content_grounding import ensure_source_grounding
from src.headline_grounding import ensure_headline_grounding
from src.production_router_policy import apply as apply_production_router_policy
from src.ranking_audit import audit_selection
from src.rtl_contract import force_rtl_blocks
from src.source_authority import resolve_source_tier
from src.story_gate import _technology_relevant
from src.youtube_parallel_discovery import fetch_youtube_items_parallel

if os.getenv("RADAR_PRODUCTION_MODE") == "1":
    apply_production_router_policy()

_original_main = pipeline.main
_original_rank = pipeline._global_ranked_selection
_original_summarize = pipeline.summarize_item
TELEGRAM_SAFE_TEXT_LIMIT = 3900
_GOOGLE_NEWS_HOSTS = {"news.google.com", "news.googleusercontent.com"}
_CANONICAL_RESOLVE_TIMEOUT_SECONDS = 6


def _contains_whole_term(text, term):
    escaped = re.escape(str(term).strip())
    return bool(re.search(rf"(?<!\w){escaped}(?!\w)", text))


def _is_critical_ai_incident(item):
    if not _technology_relevant(item):
        return False
    text = " ".join(str(item.get(key) or "") for key in ("title", "summary", "description", "source")).casefold()
    ai_hit = any(_contains_whole_term(text, term) for term in _CRITICAL_AI_TERMS)
    incident_hit = any(_contains_whole_term(text, term) for term in _CRITICAL_INCIDENT_TERMS)
    try:
        source_tier = int(item.get("source_tier", 3) or 3)
    except (TypeError, ValueError):
        source_tier = 3
    if source_tier > 2:
        source_tier = resolve_source_tier(
            source_name=item.get("source_name") or item.get("source"),
            source_url=item.get("link") or item.get("canonical_url") or item.get("url"),
            configured_tier=3,
        )
    return ai_hit and incident_hit and source_tier <= 2


def _protect_critical_incidents(items):
    protected = 0
    for item in items:
        if not _is_critical_ai_incident(item):
            continue
        item["critical_ai_incident"] = True
        item["protected_slot"] = True
        item["protected_content"] = True
        item["protected_reason"] = "critical_ai_incident"
        item["_ai_link"] = True
        protected += 1
    if protected:
        print(f"[Critical AI Incident Priority] protected={protected} source_tier<=2 incident_lane=true", flush=True)
    return items


def _resolve_google_news_url(value):
    """Resolve a Google News wrapper to a publisher URL when the redirect actually leaves Google News."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        host = urlsplit(raw).netloc.lower().split(":", 1)[0]
    except (ValueError, AttributeError):
        return raw
    if host not in _GOOGLE_NEWS_HOSTS:
        return raw
    try:
        response = requests.get(
            raw,
            allow_redirects=True,
            timeout=_CANONICAL_RESOLVE_TIMEOUT_SECONDS,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AI-Future-Radar/1.0; +https://github.com/jamshidimoh/AI-Future-Radar)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        resolved = str(response.url or raw).strip()
        response.close()
        try:
            resolved_host = urlsplit(resolved).netloc.lower().split(":", 1)[0]
        except (ValueError, AttributeError):
            resolved_host = ""
        if not resolved or resolved_host in _GOOGLE_NEWS_HOSTS:
            return raw
        return resolved
    except (requests.RequestException, ValueError, AttributeError, TypeError) as exc:
        print(f"[Canonical Source Resolution] fallback=google_news_wrapper reason={type(exc).__name__}", flush=True)
        logger.warning("Google News wrapper resolution failed: %s", exc, exc_info=True)
        return raw


def _resolve_selected_source_urls(items):
    """Promote publisher URLs for the small set of selected candidates only."""
    resolved_count = 0
    attempted = 0
    unresolved = 0
    for item in items or []:
        original = str(item.get("link") or item.get("canonical_url") or item.get("url") or "").strip()
        if not original:
            continue
        try:
            original_host = urlsplit(original).netloc.lower().split(":", 1)[0]
        except (ValueError, AttributeError):
            original_host = ""
        if original_host in _GOOGLE_NEWS_HOSTS:
            attempted += 1
        resolved = _resolve_google_news_url(original)
        if resolved and resolved != original:
            item["discovery_link"] = original
            item["link"] = resolved
            item["canonical_url"] = resolved
            resolved_count += 1
            print(f"[Canonical Source Resolution] resolved=true domain={urlsplit(resolved).netloc.lower()}", flush=True)
        elif original_host in _GOOGLE_NEWS_HOSTS:
            unresolved += 1
    if attempted:
        print(f"[Canonical Source Resolution] attempted={attempted} resolved={resolved_count} unresolved={unresolved}", flush=True)
    return items


def _production_select(items, max_posts, max_per_source, max_per_type, policy):
    """Use the canonical period ranking implementation for production."""
    _protect_critical_incidents(items)
    selected = _original_rank(
        items,
        max_posts=max_posts,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
        policy=policy,
    )
    _resolve_selected_source_urls(selected)
    print(f"[Production Selection] canonical_period_rank=true total={len(selected)}", flush=True)
    return selected
