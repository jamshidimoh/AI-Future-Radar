import json
from pathlib import Path

import pytest

from src.mission_selector import mission_score


CASES = json.loads(
    (Path(__file__).parent / "golden_editorial_cases.json").read_text(encoding="utf-8")
)["cases"]


def score_for(title: str) -> float:
    return float(mission_score(title, ""))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_golden_editorial_replay(case):
    score = score_for(case["title"])
    # Golden cases intentionally test separation between mission relevance
    # and editorial publishability. Routine applications must not outrank
    # genuine frontier/scientific signals.
    if case["expected"] == "publish":
        assert score >= 45, (case["id"], score)
    else:
        assert score < 45, (case["id"], score)


def test_frontier_signals_dominate_routine_applications():
    frontier = [
        score_for(c["title"])
        for c in CASES
        if c["expected"] == "publish"
    ]
    routine = [
        score_for(c["title"])
        for c in CASES
        if c["expected"] == "deprioritize"
    ]
    assert min(frontier) > max(routine)
