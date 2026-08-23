"""Behavioral contract benchmark for the canonical ranking layer.

This benchmark is intentionally synthetic. It validates ranking invariants
without pretending to measure production news quality. Production calibration
must use persisted real-run audit records.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# The benchmark lives under tools/, while the production module is at repo root.
# Make the repository root importable when Actions executes this file directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from period_ranked_pipeline import canonical_rank_score


CASES = [
    {
        "id": "authority_hype",
        "title": "Famous leader makes a vague future prediction",
        "editorial_score_pre_signal": 58,
        "signal_score": 38,
        "priority_person_bonus_legacy": 50,
        "_rank_is_tier0": True,
    },
    {
        "id": "substantive_interview",
        "title": "Tier-0 leader gives evidence-rich technical interview",
        "editorial_score_pre_signal": 84,
        "signal_score": 82,
        "priority_person_bonus_legacy": 50,
        "_rank_is_tier0": True,
    },
    {
        "id": "model_release",
        "title": "Primary-source release of a technically significant model",
        "editorial_score_pre_signal": 88,
        "signal_score": 91,
        "model_release_bonus_legacy": 15,
    },
    {
        "id": "paper",
        "title": "Peer-reviewed breakthrough with strong evidence",
        "editorial_score_pre_signal": 90,
        "signal_score": 89,
    },
    {
        "id": "viral",
        "title": "Viral claim with weak evidence",
        "editorial_score_pre_signal": 55,
        "signal_score": 30,
    },
]


def main() -> int:
    scores = {case["id"]: canonical_rank_score(case) for case in CASES}

    # Authority and legacy bonuses must not alter canonical score.
    base = dict(CASES[0])
    boosted = dict(base)
    boosted["priority_person_bonus_legacy"] = 999
    boosted["leader_source_authority"] = 999
    assert canonical_rank_score(base) == canonical_rank_score(boosted)

    model_a = dict(CASES[2])
    model_b = dict(model_a)
    model_b["model_release_bonus_legacy"] = 999
    assert canonical_rank_score(model_a) == canonical_rank_score(model_b)

    # Evidence-rich substantive content must beat the vague authority-only case.
    assert scores["substantive_interview"] > scores["authority_hype"]

    # Weak viral content must not outrank strong technical evidence.
    assert scores["paper"] > scores["viral"]
    assert scores["model_release"] > scores["viral"]

    output = Path("ranking_behavioral_benchmark.json")
    output.write_text(
        json.dumps({"scores": scores, "status": "PASS"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "scores": scores}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
