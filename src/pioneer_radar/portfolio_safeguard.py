"""Mission-portfolio safeguards: no routine story without an analytical anchor."""
from __future__ import annotations

ANCHOR_FIELDS = (
    "research_signal", "frontier_signal", "future_signal", "trend_signal", "leader_signal",
    "pioneer_name", "cross_domain_convergence", "epistemic_tension_id", "deep_source_weight",
)
ANCHOR_MIN_WEIGHT = 0.60


def analytical_anchor(item: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if item.get("research_signal"):
        reasons.append("research")
    if str(item.get("content_type") or "").lower() in {"research", "paper", "study", "preprint"}:
        reasons.append("research_evidence")
    if item.get("frontier_signal"):
        reasons.append("frontier")
    if item.get("future_signal") or item.get("trend_signal"):
        reasons.append("future_trend")
    if item.get("leader_signal") or item.get("pioneer_name"):
        reasons.append("pioneer")
    if float(item.get("cross_domain_convergence", 0) or 0) >= 7:
        reasons.append("cross_domain")
    if item.get("epistemic_tension_id"):
        reasons.append("epistemic_tension")
    if float(item.get("deep_source_weight", 0) or 0) >= ANCHOR_MIN_WEIGHT:
        reasons.append("deep_source")
    try:
        effective_tier = int(item.get("source_tier_effective", item.get("source_tier", 3)) or 3)
    except (TypeError, ValueError):
        effective_tier = 3
    if effective_tier <= 2 and float(item.get("editorial_score", 0) or 0) >= 20:
        reasons.append("authoritative_source")
    return bool(reasons), reasons


def filter_without_anchor(items: list[dict]) -> tuple[list[dict], list[dict]]:
    anchored, unanchored = [], []
    for item in items:
        ok, reasons = analytical_anchor(item)
        item["analytical_anchor"] = ok
        item["analytical_anchor_reasons"] = reasons
        (anchored if ok else unanchored).append(item)
    return anchored, unanchored
