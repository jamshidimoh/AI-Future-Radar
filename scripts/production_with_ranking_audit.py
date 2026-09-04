"""Production launcher with canonical period ranking and audit."""
from __future__ import annotations

import html
import re
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


def _telegram_visible_length(text):
    """Measure the post-entity text Telegram actually counts for sendMessage."""
    raw = str(text or "")
    raw = re.sub(r"<[^>]*>", "", raw)
    return len(html.unescape(raw))


def _publication_contract_visible_length(post):
    """Keep the publication contract consistent with Telegram's visible text budget."""
    return _telegram_visible_length(post)


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
    """Fit one complete Telegram story while preserving the full publication contract."""
    candidate = dict(item or {})
    post = force_rtl_blocks(formatter(candidate, source_name, link, **kwargs))
    if _telegram_visible_length(post) <= TELEGRAM_SAFE_TEXT_LIMIT:
        print(
            f"[Telegram Payload Fit] visible_length={_telegram_visible_length(post)} limit={TELEGRAM_SAFE_TEXT_LIMIT}; href attributes excluded",
            flush=True,
        )
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

    attempts = [
        (original["title"][:180], original["summary"][:800], original["why"][:300], ""),
        (original["title"][:160], original["summary"][:650], original["why"][:200], ""),
        (original["title"][:140], original["summary"][:500], original["why"][:120], ""),
        (original["title"][:120], original["summary"][:350], "", ""),
        (original["title"][:100], original["summary"][:250], "", ""),
    ]
    for title, summary, why, quote in attempts:
        rendered = render(title, summary, why, quote)
        visible_length = _telegram_visible_length(rendered)
        if visible_length <= TELEGRAM_SAFE_TEXT_LIMIT:
            print(
                f"[Telegram Payload Fit] compacted visible_length={visible_length} limit={TELEGRAM_SAFE_TEXT_LIMIT}; href attributes excluded",
                flush=True,
            )
            return rendered

    title = original["title"][:100]
    lo, hi, best = 0, len(original["summary"]), ""
    while lo <= hi:
        mid = (lo + hi) // 2
        rendered = render(title, original["summary"][:mid], "", "")
        if _telegram_visible_length(rendered) <= TELEGRAM_SAFE_TEXT_LIMIT:
            best = rendered
            lo = mid + 1
        else:
            hi = mid - 1
    if best:
        print(
            f"[Telegram Payload Fit] adaptive summary compaction visible_length={_telegram_visible_length(best)} limit={TELEGRAM_SAFE_TEXT_LIMIT}; href attributes excluded",
            flush=True,
        )
        return best

    print(
        f"[Telegram Payload Fit] unable to fit visible payload length={_telegram_visible_length(post)}; publication blocked",
        flush=True,
    )
    return ""


def _audited_main(hooks=None):
    merged = dict(hooks or {})
    explicit_select = merged.get("select_editorial")
    original_format = merged.get("format_post")
    original_summarize = merged.get("summarize_item") or _original_summarize
    original_deliver = merged.get("send_to_telegram_safe") or pipeline.send_to_telegram_safe

    # The publication contract is shared with main.py. Patch its validator at
    # runtime so the final pre-transport gate uses exactly the same visible-text
    # semantics as the production payload fitter. HTML href attributes are not
    # Telegram-visible message text and must not consume the 3900-char budget.
    import publication_contract as _publication_contract

    def visible_publication_validator(post, *, content_type="news"):
        text = str(post or "")
        if not text.strip():
            return False, "empty_payload"
        visible_length = _publication_contract_visible_length(text)
        if visible_length > TELEGRAM_SAFE_TEXT_LIMIT:
            return False, f"oversized_payload:{visible_length}>{TELEGRAM_SAFE_TEXT_LIMIT}"
        return True, "ok"

    _publication_contract.validate_publication_payload = visible_publication_validator

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
        text_length = _telegram_visible_length(text)
        if not text.strip():
            print("[Telegram Delivery Guard] blocked empty publication payload", flush=True)
            return False
        if text_length > TELEGRAM_SAFE_TEXT_LIMIT:
            print(
                f"[Telegram Delivery Guard] blocked oversized visible single-story payload length={text_length} limit={TELEGRAM_SAFE_TEXT_LIMIT}; href attributes excluded; no chunking/no partial publication",
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
