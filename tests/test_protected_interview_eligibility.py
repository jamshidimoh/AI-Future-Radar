"""Production invariant: a new, evidenced leader interview must enter Tier-0 eligibility.

This is deliberately a routing test, not a ranking-score test. A protected
interview must be selected before the normal pool is considered, so provider
exhaustion or a full normal quota cannot make it disappear.
"""

from period_ranked_pipeline import _eligibility_split


def test_new_evidenced_leader_interview_is_reserved_before_normal_pool():
    interview = {
        "leader": "Christof Koch",
        "watch_person": "Christof Koch",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_named_leader_interview": True,
        "content_type": "interview",
        "source": "Lex Fridman Podcast",
        "editorial_score": 10,
        "published": "2026-08-24T19:00:00Z",
        "interview_evidence": {"explicit": True},
    }
    normal_pool = [
        {"title": f"normal-{i}", "content_type": "news", "editorial_score": 100 - i}
        for i in range(20)
    ]

    protected, regular = _eligibility_split([interview, *normal_pool], max_protected=2)

    assert len(protected) == 1
    assert protected[0]["leader"] == "Christof Koch"
    assert protected[0]["protected_content"] is True
    assert protected[0]["_rank_is_tier0"] is True
    assert all(x.get("leader") != "Christof Koch" for x in regular)


def test_interview_evidence_does_not_protect_a_leader_mention():
    mention = {
        "leader": "Christof Koch",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_named_leader_interview": True,
        "content_type": "interview",
        "source": "Google News",
        "title": "Christof Koch discusses a new consciousness paper",
    }
    protected, regular = _eligibility_split([mention], max_protected=2)
    assert protected == []
    assert len(regular) == 1
