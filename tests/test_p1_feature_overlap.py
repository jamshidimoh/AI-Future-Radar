from __future__ import annotations

import json
import math
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from editorial_clean import enrich_items as enrich_editorial_items
from signal_engine import enrich_with_signal

FIXTURE = Path(__file__).parent / "fixtures" / "p1_golden_dataset.json"


def _load_cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _enriched_cases() -> list[dict]:
    raw = [deepcopy(case) for case in _load_cases()]
    editorial = enrich_editorial_items(raw, leader_priorities={}, source_history=[], policy={})
    return [enrich_with_signal(item) for item in editorial]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    return None if den == 0 else sum(x * y for x, y in zip(dx, dy)) / den


def _rank(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        rank = (i + j - 1) / 2 + 1
        for k in range(i, j):
            ranks[indexed[k][0]] = rank
        i = j
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    return _pearson(_rank(xs), _rank(ys))


def _editorial_vectors(items: list[dict]) -> dict[str, list[float]]:
    return {
        "freshness": [10.0 if (x.get("freshness_hours") is not None and x["freshness_hours"] <= 24) else 8.0 if (x.get("freshness_hours") is not None and x["freshness_hours"] <= 48) else 6.0 if (x.get("freshness_hours") is not None and x["freshness_hours"] <= 72) else 4.0 if (x.get("freshness_hours") is not None and x["freshness_hours"] <= 168) else 1.0 for x in items],
        "novelty": [float(x.get("novelty_score", 0) or 0) for x in items],
        "future_impact": [float(x.get("future_relevance", 0) or 0) for x in items],
        "source_quality": [float(x.get("scientific_credibility", 0) or 0) for x in items],
        "expert_influence": [float(x.get("leader_priority", 0) or 0) for x in items],
    }


def _signal_vectors(items: list[dict]) -> dict[str, list[float]]:
    return {
        key: [float(x.get("signal_vector", {}).get(key, 0) or 0) for x in items]
        for key in ("freshness", "novelty", "future_impact", "source_quality", "expert_influence")
    }


def test_p1_feature_overlap_correlation_report():
    items = _enriched_cases()
    editorial = _editorial_vectors(items)
    signal = _signal_vectors(items)
    pairs = [("freshness", "freshness"), ("novelty", "novelty"), ("future_impact", "future_impact"), ("source_quality", "source_quality"), ("expert_influence", "expert_influence")]

    print(f"P1_FEATURE_OVERLAP_CASES cases={len(items)}")
    for ekey, skey in pairs:
        xs, ys = editorial[ekey], signal[skey]
        print(
            f"P1_FEATURE_OVERLAP pair={ekey}:{skey} "
            f"pearson={_pearson(xs, ys)!r} spearman={_spearman(xs, ys)!r} "
            f"editorial_unique={len(set(xs))} signal_unique={len(set(ys))}"
        )

    editorial_contrib = {
        "freshness": [x * 0.10 for x in editorial["freshness"]],
        "novelty": [x * 0.10 for x in editorial["novelty"]],
        "future_impact": [x * 0.15 for x in editorial["future_impact"]],
        "source_quality": [x * 0.30 for x in editorial["source_quality"]],
    }
    signal_contrib = {
        "freshness": [x * 0.10 for x in signal["freshness"]],
        "novelty": [x * 0.15 for x in signal["novelty"]],
        "future_impact": [x * 0.20 for x in signal["future_impact"]],
        "source_quality": [x * 0.10 for x in signal["source_quality"]],
    }
    for key in editorial_contrib:
        e_total = sum(editorial_contrib[key])
        s_total = sum(signal_contrib[key])
        print(f"P1_FEATURE_CONTRIB feature={key} editorial_weighted_sum={e_total:.4f} signal_weighted_sum={s_total:.4f}")

    assert len(items) == 12
