"""Production launcher that adds a read-only ranking audit hook."""
from __future__ import annotations

import period_ranked_pipeline as pipeline
from src.ranking_audit import audit_selection

_original_select = pipeline.select_editorial


def _audited_select(items, max_posts, max_per_source, max_per_type, policy):
    selected = _original_select(items, max_posts, max_per_source, max_per_type, policy)
    audit_selection(selected)
    return selected


pipeline.select_editorial = _audited_select

import production_resilient_runner  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
