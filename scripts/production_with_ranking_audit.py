"""Production launcher that adds a read-only ranking audit hook."""
from __future__ import annotations

import period_ranked_pipeline as pipeline
from src.ranking_audit import audit_selection

_original_main = pipeline.main


def _audited_main(hooks=None):
    merged = dict(hooks or {})
    original_select = merged.get("select_editorial")
    if original_select is None:
        return _original_main(hooks=merged)

    def audited_select(items, max_posts, max_per_source, max_per_type, policy):
        selected = original_select(items, max_posts, max_per_source, max_per_type, policy)
        audit_selection(selected)
        return selected

    merged["select_editorial"] = audited_select
    return _original_main(hooks=merged)


pipeline.main = _audited_main

import production_resilient_runner  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
