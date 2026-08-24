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

_original_main = pipeline.main


def _audited_main(hooks=None):
    merged = dict(hooks or {})
    base_select = merged.get("select_editorial") or select_normal_portfolio

    def audited_select(items, max_posts, max_per_source, max_per_type, policy):
        selected = base_select(items, max_posts, max_per_source, max_per_type, policy)
        audit_selection(selected)
        return selected

    merged["select_editorial"] = audited_select
    return _original_main(hooks=merged)


pipeline.main = _audited_main

import production_resilient_runner  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
