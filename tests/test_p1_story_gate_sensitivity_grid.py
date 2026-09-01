from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from editorial_clean import enrich_items as enrich_editorial_items
from signal_engine import enrich_with_signal
from story_identity import deduplicate_stories

FIXTURE = Path(__file__).parent / "fixtures" / "p1_golden_dataset.json"
PRE_DELTAS = (-4.0, -2.0, 0.0, 2.0, 4.0)
SIGNAL_DELTAS = (-10.0, -5.0, 0.0, 5.0, 10.0)


def _load_cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _current_rank_key(item: dict) -> tuple:
    return (
        int(item.get("leader_priority", 0) or 0),
        int(item.get("leader_source_authority", 0) or 0),
        1 if item.get("protected_content") else 0,
        float(item.get("editorial_score", 0) or 0),
        float(item.get("signal_score", 0) or 0),
        str(item.get("published", "")),
    )


def _counterfactual_rank_key(item: dict) -> tuple:
    return (
        int(item.get("leader_priority", 0) or 0),
        int(item.get("leader_source_authority", 0) or 0),
        1 if item.get("protected_content") else 0,
        float(item.get("editorial_score_pre_signal", item.get("editorial_score", 0)) or 0),
        float(item.get("signal_score", 0) or 0),
        str(item.get("published", "")),
    )


def _enriched_cases() -> list[dict]:
    raw = [deepcopy(case) for case in _load_cases()]
    editorial = enrich_editorial_items(raw, leader_priorities={}, source_history=[], policy={})
    return [enrich_with_signal(item) for item in editorial]


def test_story_gate_representative_sensitivity_grid():
    cases = _enriched_cases()
    changed = 0
    comparisons = 0
    per_case: dict[str, int] = {}

    for base in cases:
        case_changes = 0
        base_pre = float(base.get("editorial_score", 0) or 0)
        base_signal = float(base.get("signal_score", 0) or 0)
        for pre_delta in PRE_DELTAS:
            for signal_delta in SIGNAL_DELTAS:
                left = deepcopy(base)
                right = deepcopy(base)
                left["variant"], right["variant"] = "left", "right"

                left["editorial_score_pre_signal"] = round(max(0.0, base_pre + pre_delta), 2)
                left["signal_score"] = round(max(0.0, base_signal + signal_delta), 2)
                left["editorial_score"] = round(left["editorial_score_pre_signal"] + 0.30 * left["signal_score"], 2)

                right["editorial_score_pre_signal"] = round(max(0.0, base_pre - pre_delta), 2)
                right["signal_score"] = round(max(0.0, base_signal - signal_delta), 2)
                right["editorial_score"] = round(right["editorial_score_pre_signal"] + 0.30 * right["signal_score"], 2)

                current = sorted([left, right], key=_current_rank_key, reverse=True)
                counterfactual = sorted([left, right], key=_counterfactual_rank_key, reverse=True)
                flip = current[0]["variant"] != counterfactual[0]["variant"]
                changed += int(flip)
                case_changes += int(flip)
                comparisons += 1

                current_survivor = deduplicate_stories(current)[0]
                counterfactual_survivor = deduplicate_stories(counterfactual)[0]
                assert current_survivor["variant"] == current[0]["variant"]
                assert counterfactual_survivor["variant"] == counterfactual[0]["variant"]

        per_case[str(base.get("id"))] = case_changes

    print(
        f"P1_STORY_GATE_GRID total_cases={len(cases)} comparisons={comparisons} "
        f"representative_order_changes={changed} flip_rate={changed / comparisons:.4f}"
    )
    print("P1_STORY_GATE_GRID_CASES " + ", ".join(f"{case}={count}" for case, count in per_case.items()))
    assert comparisons == len(cases) * len(PRE_DELTAS) * len(SIGNAL_DELTAS)
