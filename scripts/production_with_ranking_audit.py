"""Production launcher with canonical period ranking and audit."""
from __future__ import annotations

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
