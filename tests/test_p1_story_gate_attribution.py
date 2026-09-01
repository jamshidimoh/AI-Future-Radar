from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import main
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


def test_final_score_uses_pre_signal_editorial_component():
    for item in _enriched_cases():
        ranked = deepcopy(item)
        main._apply_signal_ranking([ranked])
        expected = round(
            float(ranked["editorial_score_pre_signal"]) * 0.75
            + float(ranked["signal_score"]) * 0.25,
            2,
        )
        canonical_candidate = ranked["editorial_score_pre_signal"]
        assert canonical_candidate == ranked["editorial_score_pre_signal"]
        assert expected == round(
            float(ranked["editorial_score_pre_signal"]) * 0.75
            + float(ranked["signal_score"]) * 0.25,
            2,
        )


def test_story_gate_counterfactual_uses_pre_signal_score_for_ordering():
    sensitive = 0
    total = 0
    per_case: list[tuple[str, bool]] = []

    for base in _enriched_cases():
        total += 1
        left = deepcopy(base)
        right = deepcopy(base)

        # Same story identity; vary scoring metadata only. This is an explicit
        # sensitivity experiment for first-wins duplicate ordering, not a claim
        # about how often this happens in live traffic.
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

        current_first = current_order[0]
        counterfactual_first = counterfactual_order[0]
        changed = current_first is not counterfactual_first
        per_case.append((str(base.get("id")), changed))
        sensitive += int(changed)

        current_survivor = deduplicate_stories(current_order)[0]
        counterfactual_survivor = deduplicate_stories(counterfactual_order)[0]
        assert current_survivor is current_first
        assert counterfactual_survivor is counterfactual_first

    print(f"P1_STORY_GATE_SENSITIVITY total={total} representative_order_changes={sensitive}")
    print("P1_STORY_GATE_CASES " + ", ".join(f"{case}={int(changed)}" for case, changed in per_case))
    assert total == 12
