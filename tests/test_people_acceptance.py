from production_entrypoint import _people_bootstrap_batch
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


def test_people_bootstrap_exact_30_is_accepted():
    ok, message = validate(_people_log())
    assert ok, message


def test_people_bootstrap_partial_progress_is_accepted():
    ok, message = validate(_people_log(delivered=29, baseline=30, status="in_progress"))
    assert ok, message
    assert "partial delivery is valid progress" in message



def test_people_bootstrap_batch_is_freshness_first_and_tightly_bounded():
    items = [
        {"people_lane": True, "people_bootstrap": True, "title": f"Person {i}", "published": f"2026-09-{10+i:02d} 10:00"}
        for i in range(10)
    ]
    batch = _people_bootstrap_batch(items)
    assert len(batch) == 2
    assert [item["title"] for item in batch] == ["Person 9", "Person 8"]
