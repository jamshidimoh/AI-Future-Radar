"""Compatibility shim for the retired legacy selector.

Production selection is owned by ``period_ranked_pipeline``. This module is
kept temporarily so stale imports fail closed without preserving the retired
selection algorithm.
"""
from __future__ import annotations


def select_content(*args, **kwargs):
    """Deprecated compatibility entry point; use the canonical selector."""
    from period_ranked_pipeline import _global_ranked_selection
    return _global_ranked_selection(*args, **kwargs)
