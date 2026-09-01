"""Canonical publication-value score.

Editorial scoring answers whether an item is suitable for publication in the
Radar. Technology-signal features remain outside this score and are owned by
``signal_engine``.
"""
from __future__ import annotations
from typing import Any

WEIGHTS = {"mission_fit": 0.30, "source_authority": 0.20, "evidence_confidence": 0.20, "publication_value": 0.15, "freshness": 0.15}


def _clip(value: Any) -> float:
    try: return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError): return 0.0


def build_features(item: dict[str, Any]) -> dict[str, float]:
    try: tier = int(item.get("source_tier", item.get("tier", 3)) or 3)
    except (TypeError, ValueError): tier = 3
    source_authority = {1: 1.0, 2: 0.75, 3: 0.45}.get(tier, 0.30)
    try: age = float(item.get("freshness_hours"))
    except (TypeError, ValueError): age = None
    freshness = 0.40 if age is None else 1.0 if age <= 24 else 0.90 if age <= 48 else 0.80 if age <= 72 else 0.60 if age <= 168 else 0.30 if age <= 720 else 0.10
    ctype = str(item.get("content_type") or "").strip().lower()
    cls = str(item.get("editorial_class") or "").strip().lower()
    if cls in {"research_breakthrough", "leader_interview"}: publication_value = 1.0
    elif ctype in {"research", "paper", "study", "interview", "podcast", "lecture", "talk", "conversation"}: publication_value = 0.90
    elif cls in {"major_industry_news", "convergence_signal", "ai_signal"}: publication_value = 0.80
    elif ctype in {"news", "official", "product_news"}: publication_value = 0.70
    else: publication_value = 0.45
    try: evidence_strength = _clip(float(item.get("evidence_strength", 0) or 0) / 10.0)
    except (TypeError, ValueError): evidence_strength = 0.0
    evidence_confidence = max(evidence_strength, 1.0 if str(item.get("evidence_text") or "").strip() else 0.0, 1.0 if item.get("research_signal") else 0.0)
    mission_fit = 1.0 if any(item.get(k) for k in ("_ai_link", "ai_relevant", "mission_area")) else 0.0
    return {"mission_fit": mission_fit, "source_authority": source_authority, "evidence_confidence": evidence_confidence, "publication_value": publication_value, "freshness": freshness}


def score_editorial_v2(item: dict[str, Any]) -> tuple[float, dict[str, float]]:
    features = build_features(item)
    return round(sum(features[k] * WEIGHTS[k] for k in WEIGHTS) * 100.0, 2), features
