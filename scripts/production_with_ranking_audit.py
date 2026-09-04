"""Production launcher with canonical period ranking and audit."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import period_ranked_pipeline as pipeline
from src.content_grounding import ensure_source_grounding
from src.headline_grounding import ensure_headline_grounding
from src.production_router_policy import apply as apply_production_router_policy
from src.ranking_audit import audit_selection
from src.rtl_contract import force_rtl_blocks

apply_production_router_policy()

_original_main = pipeline.main
_original_rank = pipeline._global_ranked_selection
_original_summarize = pipeline.summarize_item
TELEGRAM_SAFE_TEXT_LIMIT = 3900


def _production_select(items, max_posts, max_per_source, max_per_type, policy):
    """Use the canonical period ranking implementation for production."""
    selected = _original_rank(
        items,
        max_posts=max_posts,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
        policy=policy,
    )
    print(
        f"[Production Selection] canonical_period_rank=true total={len(selected)}",
        flush=True,
    )
    return selected


def _fit_formatted_payload(formatter, item, source_name, link, kwargs):
    """Fit one complete Telegram story while preserving the full publication contract.

    The ChatGPT navigation link is intentionally preserved. Only generated
    editorial prose is compacted; transport chunking is not used here.
    """
    candidate = dict(item or {})
    post = force_rtl_blocks(formatter(candidate, source_name, link, **kwargs))
    if len(post) <= TELEGRAM_SAFE_TEXT_LIMIT:
        return post

    original = {
        "title": str(candidate.get("title") or ""),
        "summary": str(candidate.get("summary") or ""),
        "why": str(candidate.get("why_it_matters") or ""),
        "quote": str(candidate.get("key_quote") or ""),
    }

    def render(title, summary, why, quote):
        compact = dict(candidate)
        compact["title"] = title
        compact["summary"] = summary
        compact["why_it_matters"] = why
        compact["key_quote"] = quote
        return force_rtl_blocks(formatter(compact, source_name, link, **kwargs))

    # Fast deterministic compaction ladder. Keep title + summary first;
    # remove optional quote/why before touching the ChatGPT/source navigation.
    attempts = [
        (original["title"][:180], original["summary"][:800], original["why"][:300], ""),
        (original["title"][:160], original["summary"][:650], original["why"][:200], ""),
        (original["title"][:140], original["summary"][:500], original["why"][:120], ""),
        (original["title"][:120], original["summary"][:350], "", ""),
        (original["title"][:100], original["summary"][:250], "", ""),
    ]
    for title, summary, why, quote in attempts:
        rendered = render(title, summary, why, quote)
        if len(rendered) <= TELEGRAM_SAFE_TEXT_LIMIT:
            print(
                f"[Telegram Payload Fit] compacted generated prose length={len(rendered)} limit={TELEGRAM_SAFE_TEXT_LIMIT}",
                flush=True,
            )
            return rendered

    # Final adaptive pass: preserve title and all mandatory navigation, and
    # find the largest summary that fits. This avoids false failure when the
    # fixed ChatGPT URL consumes most of Telegram's message budget.
    title = original["title"][:100]
    lo, hi, best = 0, len(original["summary"]), ""
    while lo <= hi:
        mid = (lo + hi) // 2
        rendered = render(title, original["summary"][:mid], "", "")
        if len(rendered) <= TELEGRAM_SAFE_TEXT_LIMIT:
            best = rendered
            lo = mid + 1
        else:
            hi = mid - 1
    if best:
        print(
            f"[Telegram Payload Fit] adaptive summary compaction length={len(best)} limit={TELEGRAM_SAFE_TEXT_LIMIT}",
            flush=True,
        )
        return best

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
            selected = explicit_select(
                items,
                max_posts=max_posts,
                max_per_source=max_per_source,
                max_per_type=max_per_type,
                policy=policy,
            )
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
    raise SystemExit(production_resilient_runner.main())
