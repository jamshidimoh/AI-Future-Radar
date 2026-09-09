"""Quality evidence and deterministic scoring for free-model selection.

The module is intentionally provider-neutral. It consumes normalized evidence
records and produces a Radar-specific quality score. External benchmark values
are evidence, not a hard-coded model ranking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import exp


DEFAULT_WEIGHTS = {
    "benchmark": 0.60,
    "task_fit": 0.20,
    "reliability": 0.15,
    "freshness": 0.05,
}


def _number(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def normalize_model_id(model_id: str) -> str:
    value = str(model_id or "").strip().lower()
    if value.endswith(":free"):
        value = value[:-5]
    return value


def benchmark_score(evidence: dict) -> float:
    """Convert Artificial Analysis-style indices to one 0..100 prior.

    Intelligence is dominant for Radar's editorial/analysis workload, while
    agentic and coding indices provide useful secondary evidence. Missing
    dimensions are ignored and the remaining dimensions are renormalized.
    """
    dimensions = (
        ("intelligence_index", 0.65),
        ("agentic_index", 0.20),
        ("coding_index", 0.15),
    )
    present = [(key, weight, _number(evidence.get(key), -1)) for key, weight in dimensions]
    present = [(key, weight, value) for key, weight, value in present if value >= 0]
    if not present:
        return 0.0
    total_weight = sum(weight for _, weight, _ in present)
    return round(sum(value * weight for _, weight, value in present) / total_weight, 3)


def task_fit_score(entry: dict) -> float:
    explicit = _number(entry.get("task_fit"), -1)
    if explicit >= 0:
        return max(0.0, min(100.0, explicit))
    return benchmark_score(entry)


def freshness_score(generated_at: str | None, half_life_hours: float = 168.0) -> float:
    if not generated_at:
        return 60.0
    try:
        stamp = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        age_hours = max(0.0, (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except ValueError:
        return 40.0
    return round(100.0 * exp(-age_hours / max(1.0, half_life_hours)), 3)


def quality_score(entry: dict, *, generated_at: str | None = None, weights: dict | None = None) -> float:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    benchmark = benchmark_score(entry)
    task_fit = task_fit_score(entry)
    reliability = max(0.0, min(100.0, _number(entry.get("reliability_score"), 80.0)))
    freshness = freshness_score(generated_at)
    total = (
        benchmark * _number(weights.get("benchmark"), DEFAULT_WEIGHTS["benchmark"])
        + task_fit * _number(weights.get("task_fit"), DEFAULT_WEIGHTS["task_fit"])
        + reliability * _number(weights.get("reliability"), DEFAULT_WEIGHTS["reliability"])
        + freshness * _number(weights.get("freshness"), DEFAULT_WEIGHTS["freshness"])
    )
    return round(total, 3)


def benchmark_record(benchmark: dict) -> dict:
    """Normalize an OpenRouter benchmark item into reusable evidence fields."""
    return {
        "benchmark_source": str(benchmark.get("source") or "unknown"),
        "benchmark_model_id": normalize_model_id(benchmark.get("model_permaslug")),
        "intelligence_index": _number(benchmark.get("intelligence_index"), -1),
        "agentic_index": _number(benchmark.get("agentic_index"), -1),
        "coding_index": _number(benchmark.get("coding_index"), -1),
        "benchmark_pricing": benchmark.get("pricing") or {},
    }
