"""Production launcher with mission-aware normal portfolio selection and audit."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import period_ranked_pipeline as pipeline
from src.portfolio_selection import select_normal_portfolio
from src.ranking_audit import audit_selection
from src.rtl_contract import force_rtl_blocks

_original_main = pipeline.main
_original_rank = pipeline._global_ranked_selection


def _audited_main(hooks=None):
    merged = dict(hooks or {})
    explicit_select = merged.get("select_editorial")
    original_format = merged.get("format_post")

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

        # Do not pre-select a tiny ranked window. The mission-aware selector must
        # see the full post-Story-Gate normal pool so it can trade off mission,
        # source, type, research/interview/news and source rotation.
        eligible = [
            x for x in (items or [])
            if not x.get("duplicate") and not x.get("publication_blocked")
        ]
        eligible = pipeline._exclude_published_candidates(eligible)
        pipeline._prepare_rank_features(eligible)
        normal_candidates = [
            item for item in eligible
            if not item.get("_rank_is_tier0") and not item.get("protected_content")
        ]

        selected = select_normal_portfolio(
            normal_candidates,
            max_posts=max_posts,
            max_per_source=max_per_source,
            max_per_type=max_per_type,
            policy=policy,
        )
        for normal_rank, item in enumerate(selected, 1):
            item["normal_period_rank"] = normal_rank
            item["tier0_rank"] = None
            item["period_rank"] = normal_rank
            item["publication_rank_assigned"] = True

        audit_selection(selected)
        return selected

    def rtl_format(*args, **kwargs):
        formatter = original_format or pipeline.format_post
        return force_rtl_blocks(formatter(*args, **kwargs))

    merged["select_editorial"] = production_select
    merged["format_post"] = rtl_format
    return _original_main(hooks=merged)


pipeline.main = _audited_main

import production_resilient_runner  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
