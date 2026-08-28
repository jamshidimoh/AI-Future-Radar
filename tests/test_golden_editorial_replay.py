import json
from pathlib import Path

import pytest

from src.mission_selector import mission_score


CASES = json.loads(
    (Path(__file__).parent / "golden_editorial_cases.json").read_text(encoding="utf-8")
)["cases"]


def evaluate(case: dict) -> tuple[float, dict]:
    item = dict(case.get("item") or {"title": case["title"], "summary": ""})
    score = float(mission_score(item))
    return score, item


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_golden_editorial_replay(case):
    score, item = evaluate(case)
    assert item.get("analytical_anchor") is (case["expected"] == "publish"), (
        case["id"], score, item.get("analytical_anchor_reasons")
    )


def test_frontier_and_research_signals_dominate_routine_applications():
    publish_scores = [
        evaluate(c)[0] for c in CASES if c["expected"] == "publish"
    ]
    routine_scores = [
        evaluate(c)[0] for c in CASES if c["expected"] == "deprioritize"
    ]
    assert min(publish_scores) > max(routine_scores)
