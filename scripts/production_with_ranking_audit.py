"""Production launcher with canonical period ranking and audit."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import period_ranked_pipeline as pipeline
from model_release_priority import model_release_bonus
from src.content_grounding import ensure_source_grounding
from src.headline_grounding import ensure_headline_grounding
from src.production_router_policy import apply as apply_production_router_policy
from src.ranking_audit import audit_selection
from src.rtl_contract import force_rtl_blocks
from src.source_authority import resolve_source_tier
from src.story_gate import _technology_relevant
from src.youtube_parallel_discovery import fetch_youtube_items_parallel

# Policy application is an explicit production-runtime concern. Do not mutate
# the global router merely by importing this module during unit-test collection.
if os.getenv("RADAR_PRODUCTION_MODE") == "1":
    apply_production_router_policy()

_original_main = pipeline.main
_original_rank = pipeline._global_ranked_selection
_original_summarize = pipeline.summarize_item
TELEGRAM_SAFE_TEXT_LIMIT = 3900
_GOOGLE_NEWS_HOSTS = {"news.google.com", "news.googleusercontent.com"}
_CANONICAL_RESOLVE_TIMEOUT_SECONDS = 6

# Production-only discovery optimization. Main.py keeps its public behavior;
# this launcher replaces only the slow serial YouTube transport with a bounded
# concurrent adapter that preserves Data API -> RSS -> page fallback semantics.
pipeline._pipeline.fetch_youtube_items = fetch_youtube_items_parallel
pipeline.fetch_youtube_items = fetch_youtube_items_parallel

_CRITICAL_AI_TERMS = (
    "artificial intelligence", "ai", "ai agent", "ai agents", "agent", "agents",
    "openai", "anthropic", "deepmind", "llm", "machine learning", "foundation model",
)
_CRITICAL_INCIDENT_TERMS = (
    "incident", "breach", "breached", "hack", "hacked", "hijack", "hijacked",
    "rogue", "escaped", "escape", "unauthorized", "attack", "attacked", "cyberattack",
    "misalignment", "safety failure", "security failure", "investigation", "regulator",
    "regulatory report", "safety report", "containment failure", "loss of control",
)


def _contains_whole_term(text, term):
    """Match a critical term as a token/phrase, not as an arbitrary substring."""
    escaped = re.escape(str(term).strip())
    return bool(re.search(rf"(?<!\w){escaped}(?!\w)", text))


def _is_critical_ai_incident(item):
    """Recognize consequential AI incidents only when technology relevance is independent."""
    if not _technology_relevant(item):
        return False

    text = " ".join(
        str(item.get(key) or "")
        for key in ("title", "summary", "description", "source")
    ).casefold()
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
    """Resolve a Google News wrapper to its publisher URL without touching other sources."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        host = urlsplit(raw).netloc.lower().split(":", 1)[0]
    except Exception:
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
        return resolved or raw
    except Exception as exc:
        print(f"[Canonical Source Resolution] fallback=google_news_wrapper reason={type(exc).__name__}", flush=True)
        return raw


def _resolve_selected_source_urls(items):
    """Promote publisher URLs for the small set of selected candidates only."""
    resolved_count = 0
    for item in items or []:
        original = str(item.get("link") or item.get("canonical_url") or item.get("url") or "").strip()
        if not original:
            continue
        resolved = _resolve_google_news_url(original)
        if resolved and resolved != original:
            item["discovery_link"] = original
            item["link"] = resolved
            item["canonical_url"] = resolved
            resolved_count += 1
            print(
                f"[Canonical Source Resolution] resolved=true domain={urlsplit(resolved).netloc.lower()}",
                flush=True,
            )
        elif item.get("canonical_url"):
            item["canonical_url"] = str(item["canonical_url"]).strip()
    if resolved_count:
        print(f"[Canonical Source Resolution] selected_resolved={resolved_count}", flush=True)
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
    print(
        f"[Production Selection] canonical_period_rank=true total={len(selected)}",
        flush=True,
    )
    return selected


def _without_expensive_chatgpt_row(post):
    """Remove the verbose inline ChatGPT deep-analysis URL from production payloads.

    The formatter embeds a long prompt inside the query URL. It is useful for
    interactive readers but can consume most of Telegram's single-message
    budget before editorial prose is included. The source link remains intact.
    """
    compact = re.sub(
        r"[^\n]*🧠[^\n]*بررسی بیشتر با ChatGPT[^\n]*(?:\n|$)",
        "",
        str(post or ""),
    )
    compact = re.sub(r"\n{3,}", "\n\n", compact).strip()
    if compact != str(post or "").strip():
        print("[Telegram Payload Fit] removed verbose ChatGPT deep-analysis row", flush=True)
    return compact


def _fit_formatted_payload(formatter, item, source_name, link, kwargs):
    """Keep one story inside Telegram's safe limit without transport chunking.

    Editorial structure is preserved first; the verbose inline ChatGPT row is
    removed from production messages, then only generated prose fields are
    compacted when necessary. This is intentionally production-only.
    """
    candidate = dict(item or {})
    post = _without_expensive_chatgpt_row(
        force_rtl_blocks(formatter(candidate, source_name, link, **kwargs))
    )
    if len(post) <= TELEGRAM_SAFE_TEXT_LIMIT:
        return post

    original_summary = str(candidate.get("summary") or "")
    original_why = str(candidate.get("why_it_matters") or "")
    original_quote = str(candidate.get("key_quote") or "")
    original_title = str(candidate.get("title") or "")

    def render(summary, why, quote, title):
        compact = dict(candidate)
        compact["summary"] = summary
        compact["why_it_matters"] = why
        compact["key_quote"] = quote
        compact["title"] = title
        return _without_expensive_chatgpt_row(
            force_rtl_blocks(formatter(compact, source_name, link, **kwargs))
        )

    prose = original_summary + "\n\n" + original_why
    if prose:
        lo, hi, best = 0, len(prose), ""
        while lo <= hi:
            mid = (lo + hi) // 2
            sample = prose[:mid].rstrip()
            split_at = sample.rfind("\n\n")
            if split_at > 0:
                summary = sample[:split_at].rstrip()
                why = sample[split_at + 2:].strip()
            else:
                summary, why = sample, ""
            rendered = render(summary, why, original_quote, original_title)
            if len(rendered) <= TELEGRAM_SAFE_TEXT_LIMIT:
                best = rendered
                lo = mid + 1
            else:
                hi = mid - 1
        if best:
            print("[Telegram Payload Fit] compacted generated prose to single-message limit", flush=True)
            return best

    for quote in (original_quote[:600], original_quote[:300], ""):
        for title in (original_title, original_title[:240], original_title[:160]):
            rendered = render(original_summary[:1200], original_why[:900], quote, title)
            if len(rendered) <= TELEGRAM_SAFE_TEXT_LIMIT:
                print("[Telegram Payload Fit] applied fallback compacting", flush=True)
                return rendered

    print(
        f"[Telegram Payload Fit] unable to fit payload length={len(post)}; publication blocked",
        flush=True,
    )
    return ""


def _audited_main(hooks=None):
    merged = dict(hooks or {})
    explicit_select = merged.get("select_editorial")
    original_format = merged.get("format_post")
    original_summarize = merged.get("summarize_item") or _original_summarize
    original_deliver = merged.get("send_to_telegram_safe") or pipeline.send_to_telegram_safe

    def production_select(items, max_posts, max_per_source, max_per_type, policy):
        if explicit_select is not None:
            _protect_critical_incidents(items)
            selected = explicit_select(
                items,
                max_posts=max_posts,
                max_per_source=max_per_source,
                max_per_type=max_per_type,
                policy=policy,
            )
            _resolve_selected_source_urls(selected)
            audit_selection(selected)
            return selected

        selected = _production_select(
            items,
            max_posts=max_posts,
            max_per_source=max_per_source,
            max_per_type=max_per_type,
            policy=policy,
        )
        audit_selection(selected)
        return selected

    def grounded_summarize(item):
        draft = original_summarize(item)
        if draft is None:
            return None
        source_grounded = ensure_source_grounding(draft, item)
        if source_grounded is None:
            return None
        return ensure_headline_grounding(source_grounded, item)

    def rtl_format(item, source_name, link, **kwargs):
        formatter = original_format or pipeline.format_post
        return _fit_formatted_payload(formatter, item, source_name, link, kwargs)

    def single_message_deliver(text, image_url="", source_link=""):
        text_length = len(str(text or ""))
        if not text.strip():
            print("[Telegram Delivery Guard] blocked empty publication payload", flush=True)
            return False
        if text_length > TELEGRAM_SAFE_TEXT_LIMIT:
            print(
                f"[Telegram Delivery Guard] blocked oversized single-story payload length={text_length} limit={TELEGRAM_SAFE_TEXT_LIMIT}; no chunking/no partial publication",
                flush=True,
            )
            return False
        return original_deliver(text, image_url=image_url, source_link=source_link)

    merged["select_editorial"] = production_select
    merged["summarize_item"] = grounded_summarize
    merged["format_post"] = rtl_format
    merged["send_to_telegram_safe"] = single_message_deliver
    return _original_main(hooks=merged)


pipeline.main = _audited_main

import production_resilient_runner  # noqa: E402


if __name__ == "__main__":
    # The launcher reaches __main__ only for an actual production invocation;
    # imports from tests do not activate the production routing policy.
    if os.getenv("RADAR_PRODUCTION_MODE") != "1":
        os.environ["RADAR_PRODUCTION_MODE"] = "1"
        apply_production_router_policy()
    raise SystemExit(production_resilient_runner.main())
