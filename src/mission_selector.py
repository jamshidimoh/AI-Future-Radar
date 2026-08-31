"""Legacy compatibility helper for source-tier normalization only.

Editorial portfolio construction and mission scoring live in
``unified_editorial_selection``. This module intentionally has no parallel
selection engine.
"""
from __future__ import annotations


def _source_tier(item: dict) -> int | None:
    """Return the explicit source tier when present and valid."""
    raw = item.get("source_tier", item.get("tier"))
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


__all__ = ["_source_tier"]
