"""Compatibility shim for legacy imports; production uses canonical ranking."""
from __future__ import annotations

from period_ranked_pipeline import _global_ranked_selection


def select_content(items, max_posts=4, max_per_source=2, max_per_type=2, policy=None):
    return _global_ranked_selection(
        items,
        max_posts=max_posts,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
        policy=policy or {},
    )
