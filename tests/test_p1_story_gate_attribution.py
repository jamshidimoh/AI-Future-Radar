from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from editorial_clean import enrich_items as enrich_editorial_items
from signal_engine import enrich_with_signal
from story_identity import deduplicate_stories

FIXTURE = Path(__file__).parent / "fixtures" / "p1_golden_dataset.json"


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


def test_story_gate_representative_is_sensitive_to_inflated_score():
    sensitive = 0
    total = 0
    per_case: list[tuple[str, bool]] = []

    for base in _enriched_cases():
        total += 1
        left = deepcopy(base)
        right = deepcopy(base)
        left["variant"] = "left"
        right["variant"] = "right"

        base_pre = float(base.get("editorial_score", 0) or 0)
        base_signal = float(base.get("signal_score", 0) or 0)

        left["editorial_score_pre_signal"] = base_pre
        left["signal_score"] = base_signal
        left["editorial_score"] = round(base_pre + 0.30 * base_signal, 2)

        right["editorial_score_pre_signal"] = round(base_pre + 2.0, 2)
        right["signal_score"] = round(max(0.0, base_signal - 10.0), 2)
        right["editorial_score"] = round(
            right["editorial_score_pre_signal"] + 0.30 * right["signal_score"],
            2,
        )

        current_order = sorted([left, right], key=_current_rank_key, reverse=True)
        counterfactual_order = sorted([left, right], key=_counterfactual_rank_key, reverse=True)
        changed = current_order[0]["variant"] != counterfactual_order[0]["variant"]
        per_case.append((str(base.get("id")), changed))
        sensitive += int(changed)

        current_survivor = deduplicate_stories(current_order)[0]
        counterfactual_survivor = deduplicate_stories(counterfactual_order)[0]
        assert current_survivor["variant"] == current_order[0]["variant"]
        assert counterfactual_survivor["variant"] == counterfactual_order[0]["variant"]

    print(f"P1_STORY_GATE_SENSITIVITY total={total} representative_order_changes={sensitive}")
    print("P1_STORY_GATE_CASES " + ", ".join(f"{case}={int(changed)}" for case, changed in per_case))
    assert total == 12
