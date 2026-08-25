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
from src.ranking_audit import audit_selection
from src.rtl_contract import force_rtl_blocks

_original_main = pipeline.main
_original_rank = pipeline._global_ranked_selection
_original_summarize = pipeline.summarize_item


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


def _audited_main(hooks=None):
    merged = dict(hooks or {})
    explicit_select = merged.get("select_editorial")
    original_format = merged.get("format_post")
    original_summarize = merged.get("summarize_item") or _original_summarize

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
        return force_rtl_blocks(formatter(item, source_name, link, **kwargs))

    merged["select_editorial"] = production_select
    merged["summarize_item"] = grounded_summarize
    merged["format_post"] = rtl_format
    return _original_main(hooks=merged)


pipeline.main = _audited_main

import production_resilient_runner  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
