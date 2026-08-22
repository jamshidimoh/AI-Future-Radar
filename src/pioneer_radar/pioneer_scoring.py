"""Scoring for human-intelligence signals without equating fame with truth."""
from __future__ import annotations

WEIGHTS = {
    "technology_impact": 0.25,
    "scientific_authority": 0.20,
    "future_vision": 0.20,
    "public_influence": 0.15,
    "trend_score": 0.10,
    "audience_score": 0.10,
}


def pioneer_score(profile: dict) -> float:
    score = sum(float(profile.get(k, 0) or 0) * weight for k, weight in WEIGHTS.items())
    return round(score * 10.0, 2)


def attach_pioneer_signal(item: dict, profile: dict) -> dict:
    out = dict(item)
    out["pioneer_name"] = profile.get("name")
    out["pioneer_category"] = profile.get("category")
    out["pioneer_score"] = pioneer_score(profile)
    out["pioneer_priority"] = int(profile.get("priority", 0) or 0)
    out["pioneer_trend_score"] = float(profile.get("trend_score", 0) or 0)
    out["pioneer_audience_score"] = float(profile.get("audience_score", 0) or 0)
    return out
