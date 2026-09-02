"""Deterministic temporal intelligence for persisted Radar trends.

G4 consumes observation history without changing publication behavior. It
measures persistence, slope/acceleration, transient spikes, and periodicity.
"""
from __future__ import annotations

import json
import math
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
DEFAULT_CONFIG: dict[str, Any] = {
    "recent_window": 4,
    "transient_spike_ratio": 0.75,
    "acceleration_threshold": 0.05,
    "weakening_threshold": -0.05,
    "minimum_periodic_observations": 6,
    "max_period": 12,
}


def validate_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(dict(config or {}))
    cfg["recent_window"] = int(cfg["recent_window"])
    cfg["transient_spike_ratio"] = float(cfg["transient_spike_ratio"])
    cfg["acceleration_threshold"] = float(cfg["acceleration_threshold"])
    cfg["weakening_threshold"] = float(cfg["weakening_threshold"])
    cfg["minimum_periodic_observations"] = int(cfg["minimum_periodic_observations"])
    cfg["max_period"] = int(cfg["max_period"])
    if cfg["recent_window"] < 2:
        raise ValueError("recent_window must be >= 2")
    if not 0.0 < cfg["transient_spike_ratio"] <= 1.0:
        raise ValueError("transient_spike_ratio must be in (0, 1]")
    if cfg["acceleration_threshold"] <= 0 or cfg["weakening_threshold"] >= 0:
        raise ValueError("acceleration/weakening thresholds must straddle zero")
    if cfg["minimum_periodic_observations"] < 4:
        raise ValueError("minimum_periodic_observations must be >= 4")
    if cfg["max_period"] < 2:
        raise ValueError("max_period must be >= 2")
    return cfg


def _linear_slope(points: Sequence[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    x_bar = sum(x for x, _ in points) / len(points)
    y_bar = sum(y for _, y in points) / len(points)
    denominator = sum((x - x_bar) ** 2 for x, _ in points)
    if denominator == 0:
        return 0.0
    return sum((x - x_bar) * (y - y_bar) for x, y in points) / denominator


def _periodicity(values: Sequence[int], max_period: int, minimum_observations: int) -> tuple[int | None, float]:
    n = len(values)
    if n < minimum_observations:
        return None, 0.0
    upper = min(max_period, n // 2)
    best_period: int | None = None
    best_score = 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values)
    if variance == 0:
        return None, 0.0
    for period in range(2, upper + 1):
        pairs = [(i, i - period) for i in range(period, n)]
        covariance = sum((values[i] - mean) * (values[j] - mean) for i, j in pairs)
        denom = math.sqrt(sum((values[i] - mean) ** 2 for i, _ in pairs) * sum((values[j] - mean) ** 2 for _, j in pairs))
        score = covariance / denom if denom else 0.0
        if score > best_score + 1e-12 or (abs(score - best_score) <= 1e-12 and score > 0 and (best_period is None or period < best_period)):
            best_period = period
            best_score = score
    return best_period, round(max(0.0, min(1.0, best_score)), 3)


def analyze_trend_observations(
    trend_id: str,
    observations: Iterable[Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = validate_config(config)
    rows = []
    for observation in observations:
        if str(observation.get("cluster_id") or "") != str(trend_id):
            continue
        run_index = int(observation.get("run_index"))
        score = float(observation.get("trend_score", 0.0) or 0.0)
        state = str(observation.get("state") or "active")
        rows.append((run_index, score, state))
    rows.sort(key=lambda row: row[0])
    if not rows:
        raise ValueError("no observations for trend_id")
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError("duplicate run_index for trend")

    run_indices = [row[0] for row in rows]
    scores = [row[1] for row in rows]
    present = [1 if row[2] in {"active", "revived"} else 0 for row in rows]
    gaps = [run_indices[i] - run_indices[i - 1] for i in range(1, len(run_indices))]
    observed_span = max(1, run_indices[-1] - run_indices[0] + 1)
    persistence_ratio = sum(present) / max(1, observed_span)
    recent = rows[-cfg["recent_window"] :]
    recent_points = [(float(row[0]), row[1]) for row in recent]
    all_points = [(float(row[0]), row[1]) for row in rows]
    slope = _linear_slope(all_points)
    recent_slope = _linear_slope(recent_points)
    previous = rows[:-cfg["recent_window"]] if len(rows) > cfg["recent_window"] else rows[:]
    previous_slope = _linear_slope([(float(row[0]), row[1]) for row in previous])
    acceleration = recent_slope - previous_slope if len(previous) >= 2 else recent_slope

    mean_score = sum(scores) / len(scores)
    recent_mean = sum(row[1] for row in recent) / len(recent)
    peak = max(scores)
    trough = min(scores)
    spike = peak > 0 and (recent_mean <= peak * (1.0 - cfg["transient_spike_ratio"]) or (len(rows) >= 3 and scores[-1] < peak * (1.0 - cfg["transient_spike_ratio"])))
    period, periodicity_score = _periodicity(present, cfg["max_period"], cfg["minimum_periodic_observations"])

    if spike:
        temporal_class = "transient_spike"
    elif acceleration >= cfg["acceleration_threshold"]:
        temporal_class = "accelerating"
    elif recent_slope <= cfg["weakening_threshold"]:
        temporal_class = "weakening"
    elif persistence_ratio >= 0.6:
        temporal_class = "persistent"
    else:
        temporal_class = "stable"

    return {
        "schema_version": SCHEMA_VERSION,
        "trend_id": str(trend_id),
        "first_seen_run": run_indices[0],
        "last_seen_run": run_indices[-1],
        "observation_count": len(rows),
        "observed_span_runs": observed_span,
        "persistence_ratio": round(persistence_ratio, 3),
        "mean_score": round(mean_score, 3),
        "recent_mean_score": round(recent_mean, 3),
        "peak_score": round(peak, 3),
        "trough_score": round(trough, 3),
        "score_slope": round(slope, 4),
        "recent_score_slope": round(recent_slope, 4),
        "acceleration": round(acceleration, 4),
        "max_gap_runs": max(gaps, default=0),
        "period": period,
        "periodicity_score": periodicity_score,
        "temporal_class": temporal_class,
    }


def analyze_registry(
    observations: Iterable[Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in observations:
        cluster_id = str(row.get("cluster_id") or "")
        if cluster_id:
            grouped.setdefault(cluster_id, []).append(row)
    output = [analyze_trend_observations(cluster_id, grouped[cluster_id], config) for cluster_id in sorted(grouped)]
    return json.loads(json.dumps(output, ensure_ascii=False, sort_keys=True))
