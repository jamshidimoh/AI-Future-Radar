from production_entrypoint import _people_bootstrap_batch, _people_bootstrap_evidence_line, _people_bootstrap_quality_allowed
from scripts.production_acceptance_guard import validate


def _people_log(delivered=30, baseline=30, status="complete"):
    return f"""
[People Bootstrap] required=30 discovered=30
[Production Selection] total=30
[Publication Summary Budget] input=30 output=30 normal_limit=6
[Publication Policy] PUBLISH PEOPLE person=Sam Altman score=0 quota_exempt=true cap=none
[Production Contract] normal_news=0 normal_max=3 people={delivered} people_max=none technical_trend=0 technical_max=1 mind_ideas_voices=0 mind_max=1 voices_perspectives=0 voices_max=1 tier0_news=0 strategic_analytical=0 strategic_max=1 normal_score_floor=55.0 special_lanes_score_floor=not_applied education=not_due
[People Bootstrap] status={status} delivered={delivered}/30 baseline={baseline}/30 bootstrap_at=2026-09-22T09:00:00+00:00
Posts sent: {delivered}/{delivered}
"""


def test_people_bootstrap_requires_explicit_validation_and_authority():
    valid = {"people_bootstrap": True, "people_bootstrap_validated": True, "source_tier": 1}
    weak = {"people_bootstrap": True, "people_bootstrap_validated": True, "source_tier": 3}
    unvalidated = {"people_bootstrap": True, "source_tier": 1}
    assert _people_bootstrap_quality_allowed(valid) is True
    assert _people_bootstrap_quality_allowed(weak) is False
    assert _people_bootstrap_quality_allowed(unvalidated) is False


def test_people_bootstrap_exact_30_is_accepted():
    ok, message = validate(_people_log())
    assert ok, message


def test_people_bootstrap_partial_progress_is_accepted():
    ok, message = validate(_people_log(delivered=29, baseline=30, status="in_progress"))
    assert ok, message
    assert "partial delivery is valid progress" in message



def test_people_bootstrap_batch_is_freshness_first_and_bounded():
    items = [
        {"people_lane": True, "people_bootstrap": True, "title": f"Person {i}", "published": f"2026-09-{10+i:02d} 10:00"}
        for i in range(10)
    ]
    batch = _people_bootstrap_batch(items)
    assert len(batch) == 2
    assert [item["title"] for item in batch] == ["Person 9", "Person 8"]


def _complete_bootstrap_state():
    names = [f"Person {index:02d}" for index in range(30)]
    return {
        "status": "complete",
        "people_count": 30,
        "delivered_count": 30,
        "delivered_people": names,
        "bootstrap_at": "2026-10-01T00:00:00+00:00",
        "baseline": {
            name: {
                "title": f"{name} discusses artificial intelligence",
                "link": f"https://example.org/{index}",
                "published": "2026-10-01 10:00",
            }
            for index, name in enumerate(names)
        },
    }


def test_people_bootstrap_evidence_line_matches_closure_gate_for_valid_state():
    line = _people_bootstrap_evidence_line(_complete_bootstrap_state())
    assert line.startswith("[People Bootstrap] status=complete delivered=30/30 baseline=30/30")
    assert "bootstrap_at=2026-10-01T00:00:00+00:00" in line


def test_people_bootstrap_evidence_line_fails_closed_for_inconsistent_state():
    state = _complete_bootstrap_state()
    state["delivered_people"] = state["delivered_people"][:-1]
    line = _people_bootstrap_evidence_line(state)
    assert line.startswith("[People Bootstrap] status=in_progress delivered=29/30 baseline=30/30")


def test_people_bootstrap_evidence_line_records_missing_state_without_claiming_complete():
    line = _people_bootstrap_evidence_line(None)
    assert line.startswith("[People Bootstrap] status=in_progress delivered=0/30 baseline=0/30")
