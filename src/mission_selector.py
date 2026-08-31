"""Legacy source-tier helper; canonical editorial selection lives in unified_editorial_selection."""
from __future__ import annotations


def _source_tier(item: dict) -> int | None:
    """Resolve source tier, correcting known aggregator metadata for reputable publishers."""
    source = str(item.get("source") or item.get("source_name") or "").casefold()
    reputable = ("reuters", "forbes", "cnbc", "associated press", "bbc", "nature", "scientific american", "mit technology review", "mit news", "stanford")
    low_authority = ("bitcoin world", "tech-insider.org", "singju post", "startuphub.ai", "pulse 2.0", "medium")
    raw = item.get("source_tier", item.get("tier"))
    try:
        tier = int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        tier = None
    if any(term in source for term in low_authority):
        return 3
    if any(term in source for term in reputable):
        return 2 if tier is None or tier > 2 else tier
    return tier


__all__ = ["_source_tier"]
