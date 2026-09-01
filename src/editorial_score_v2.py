"""Canonical publication-value scoring model.

This layer answers: "How suitable is this item for the Radar's editorial mission?"
Technology-signal features such as novelty and future-impact are intentionally
excluded because those belong to ``signal_engine``.
"""
from __future__ import annotations

from typing import Any


WEIGHTS = {
    "mission_fit": 0.30,
    "source_authority": 0.20,
    "evidence_confidence": 0.20,
    "publication_value": 0.15,
    "freshness": 0.15,
}


def _clip(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _tier_quality(item: dict[str, Any]) -> float:
    try:
        tier = int(item.get("source_tier", item.get("tier", 3)) or 3)
    except (TypeError, ValueError):
        tier = 3
    return {1: 1.0, 2: 0.75, 3: 0.45}.get(tier, 0.30)


def _freshness(item: dict[str, Any]) -> float:
    try:
        age = float(item.get("freshness_hours"))
    except (TypeError, ValueError):
        return 0.40
    if age <= 24:
        return 1.0
    if age <= 48:
        return 0.90
    if age <= 72:
        return 0.80
    if age <= 168:
        return 0.60
    if age <= 720:
        return 0.30
    return 0.10


def _publication_value(item: dict[str, Any]) -> float:
    content_type = str(item.get("content_type") or "").strip().lower()
    editorial_class = str(item.get("editorial_class") or "").strip().lower()
    if editorial_class in {"research_breakthrough", "leader_interview"}:
        return 1.0
    if content_type in {"research", "paper", "study", "interview", "podcast", "lecture", "talk", "conversation"}:
        return 0.90
    if editorial_class in {"major_industry_news", "convergence_signal", "ai_signal"}:
        return 0.80
    if content_type in {"news", "official", "product_news"}:
        return 0.70
    return 0.45


def build_features(item: dict[str, Any]) -> dict[str, float]:
    mission_fit = 1.0 if item.get("_ai_link") or item.get("ai_relevant") or item.get("mission_area") else 0.0
    explicit_evidence = bool(str(item.get("evidence_text") or "").strip())
    research_signal = bool(item.get("research_signal"))
    evidence_strength = _clip(float(item.get("evidence_strength", 0) or 0) / 10.0)
    evidence_confidence = max(evidence_strength, 1.0 if explicit_evidence or research_signal else 0.0)
    return {
        "mission_fit": mission_fit,
        "source_authority": _tier_quality(item),
        "evidence_confidence": evidence_confidence,
        "publication_value": _publication_value(item),
        "freshness": _freshness(item),
    }


def score_editorial_v2(item: dict[str, Any]) -> tuple[float, dict[str, float]]:
    features = build_features(item)
    score = sum(features[name] * WEIGHTS[name] for name in WEIGHTS) * 100.0
    return round(score, 2), features
