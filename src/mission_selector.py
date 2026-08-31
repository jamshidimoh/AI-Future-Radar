"""Compatibility helpers; canonical portfolio selection lives elsewhere."""
from __future__ import annotations

from src.portfolio_safeguard import analytical_anchor
from src.strategic_signal import strategic_forecast_score

_ROUTINE_TERMS = (
    "meal planner", "meal planning", "recipe generator", "personalized meal", "personalised meal",
    "shopping list", "routine task", "daily task", "productivity", "workflow", "customer service",
    "marketing", "content creation", "time savings", "using chatgpt", "used chatgpt", "chatgpt helped",
    "chatgpt reduced", "chatgpt saves", "chatgpt saved", "prompt", "chatgpt images", "chatgpt image",
    "image generation", "image generator", "chatgpt can now", "chatgpt update", "product update",
)
_STRONG_TERMS = (
    "new model", "model release", "new architecture", "new capability", "breakthrough",
    "state of the art", "frontier", "scientific discovery", "benchmark record", "research result",
    "experimental validation", "new reasoning capability",
)


def _source_tier(item: dict) -> int | None:
    """Return the explicit source tier when present and valid."""
    raw = item.get("source_tier", item.get("tier"))
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def mission_score(item: dict) -> float:
    """Compatibility scoring surface for historical tests; not used by production selection."""
    text = " ".join(str(item.get(k) or "") for k in ("title", "summary", "why_it_matters")).casefold()
    strategic = strategic_forecast_score(item)
    routine_hits = sum(1 for term in _ROUTINE_TERMS if term in text)
    strong = routine_hits == 0 or any(term in text for term in _STRONG_TERMS) or bool(item.get("research_signal"))
    item["routine_application_hits"] = routine_hits
    item["routine_application_strong_signal"] = strong
    anchor, reasons = analytical_anchor(item)
    item["analytical_anchor"] = anchor
    item["analytical_anchor_reasons"] = reasons
    base = float(item.get("editorial_score", 0) or 0) + float(item.get("signal_score", 0) or 0) * 0.4
    score = base + float(strategic)
    if not strong:
        score -= min(18.0, routine_hits * 6.0)
    item["mission_score"] = round(score, 2)
    return score


__all__ = ["_source_tier", "mission_score"]
