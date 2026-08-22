"""Technology signal scoring layer for AI Future Radar.

This module deliberately stays independent from editorial selection. It answers:
"How strong is the underlying technology signal?" rather than "Should we publish it?".
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

INTERVIEW_TERMS = {"interview", "conversation", "fireside", "keynote", "podcast", "discussion", "q&a", "dialogue"}
FUTURE_TERMS = {"future", "forecast", "trajectory", "implications", "next generation", "long term", "long-term", "prediction"}
NOVELTY_TERMS = {"new", "novel", "first", "breakthrough", "introduces", "introduced", "unveils", "unveiled", "new model", "new architecture"}
TECHNICAL_TERMS = {"architecture", "benchmark", "algorithm", "dataset", "optimization", "training", "inference", "reasoning", "formalism", "methodology", "ablation", "experiment"}
EVIDENCE_TERMS = {"results", "findings", "benchmark", "experiment", "measured", "peer reviewed", "peer-reviewed", "paper", "study", "data"}
TREND_TERMS = {"adoption", "surge", "shift", "trend", "trajectory", "industry", "market", "deployment", "open source", "open-weight", "agentic"}


def _text(item: dict) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')} {item.get('description', '')}".lower()


def _count_terms(text: str, terms: set[str]) -> int:
    return sum(1 for term in terms if term in text)


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, float(value)))


def _age_hours(value: str | None) -> float | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
        except ValueError:
            pass
    return None


def freshness_score(item: dict) -> float:
    age = _age_hours(str(item.get("published") or ""))
    if age is None: return 4.0
    if age <= 24: return 10.0
    if age <= 48: return 9.0
    if age <= 72: return 8.0
    if age <= 168: return 6.0
    if age <= 720: return 3.0
    return 1.0


def novelty_score(item: dict) -> float:
    text = _text(item)
    explicit = _count_terms(text, NOVELTY_TERMS)
    score = 3.0 + min(explicit * 1.5, 5.0)
    if item.get("is_new") or item.get("is_breakthrough"):
        score += 2.0
    return _clamp(score)


def future_impact_score(item: dict) -> float:
    text = _text(item)
    score = 3.0 + min(_count_terms(text, FUTURE_TERMS) * 1.2, 3.0)
    if item.get("is_leader_watch") or item.get("leader_watch_protected"):
        score += 1.5
    if str(item.get("category") or "").lower() in {"future", "trend", "futures"}:
        score += 1.5
    return _clamp(score)


def technical_significance_score(item: dict) -> float:
    text = _text(item)
    score = 2.0 + min(_count_terms(text, TECHNICAL_TERMS) * 0.9, 6.0)
    if str(item.get("content_type") or "").lower() in {"research", "paper", "study"}:
        score += 1.0
    return _clamp(score)


def strategic_relevance_score(item: dict) -> float:
    text = _text(item)
    score = 3.0 + min(_count_terms(text, {"industry", "infrastructure", "platform", "semiconductor", "robotics", "governance", "regulation", "deployment", "enterprise"}) * 0.8, 5.0)
    return _clamp(score)


def expert_influence_score(item: dict) -> float:
    explicit = item.get("expert_influence")
    if explicit is not None:
        try: return _clamp(float(explicit))
        except (TypeError, ValueError): pass
    priority = item.get("leader_priority")
    if priority is not None:
        try: return _clamp(float(priority))
        except (TypeError, ValueError): pass
    if item.get("is_leader_watch") or item.get("leader_watch_protected"):
        return 8.0
    return 2.0


def evidence_strength_score(item: dict) -> float:
    text = _text(item)
    score = 2.0 + min(_count_terms(text, EVIDENCE_TERMS) * 1.0, 6.0)
    tier = int(item.get("source_tier") or 3)
    score += {1: 2.0, 2: 1.0, 3: 0.0}.get(tier, 0.0)
    return _clamp(score)


def trend_alignment_score(item: dict) -> float:
    text = _text(item)
    score = 2.0 + min(_count_terms(text, TREND_TERMS) * 0.9, 6.0)
    if item.get("is_trending_query"): score += 1.0
    return _clamp(score)


def source_quality_score(item: dict) -> float:
    tier = int(item.get("source_tier") or 3)
    score = {1: 10.0, 2: 7.0, 3: 4.0}.get(tier, 3.0)
    if item.get("official"): score += 1.0
    return _clamp(score)


def calculate_signal_vector(item: dict) -> dict[str, float]:
    return {
        "freshness": freshness_score(item),
        "novelty": novelty_score(item),
        "future_impact": future_impact_score(item),
        "technical_significance": technical_significance_score(item),
        "strategic_relevance": strategic_relevance_score(item),
        "expert_influence": expert_influence_score(item),
        "evidence_strength": evidence_strength_score(item),
        "trend_alignment": trend_alignment_score(item),
        "source_quality": source_quality_score(item),
    }


WEIGHTS = {
    "freshness": 0.10,
    "novelty": 0.15,
    "future_impact": 0.20,
    "technical_significance": 0.15,
    "strategic_relevance": 0.10,
    "expert_influence": 0.10,
    "evidence_strength": 0.05,
    "trend_alignment": 0.05,
    "source_quality": 0.10,
}


def calculate_signal_score(vector: dict[str, float]) -> float:
    return round(sum(vector[key] * weight for key, weight in WEIGHTS.items()) * 10.0, 2)


def classify_signal(score: float) -> str:
    if score >= 80: return "very_high"
    if score >= 65: return "high"
    if score >= 50: return "medium"
    if score >= 35: return "low"
    return "very_low"


def enrich_with_signal(item: dict) -> dict:
    enriched = dict(item)
    vector = calculate_signal_vector(enriched)
    score = calculate_signal_score(vector)
    is_leader = bool(enriched.get("is_leader_watch") or enriched.get("leader_watch_protected"))
    is_interview = bool(
        str(enriched.get("content_type") or "").lower() in {"interview", "podcast", "talk", "lecture"}
        or any(term in _text(enriched) for term in INTERVIEW_TERMS)
    )
    if is_leader and is_interview:
        score = min(100.0, score + 15.0)
    enriched["signal_vector"] = vector
    enriched["signal_score"] = round(score, 2)
    enriched["signal_class"] = classify_signal(score)
    enriched["signal_interview"] = is_interview
    return enriched


def enrich_items(items: list[dict]) -> list[dict]:
    return [enrich_with_signal(item) for item in items]


def enrich_signal_items(items: list[dict]) -> list[dict]:
    """Compatibility entrypoint used by main.py; preserve the signal-engine API."""
    return enrich_items(items)
