from period_ranked_pipeline import _eligibility_split


def test_leader_activity_enters_protected_pool():
    item = {
        "title": "Andrew Ng announces a new AI initiative",
        "content_type": "official",
        "summary": "A short announcement about a new initiative and its organizational implications.",
        "leader": "Andrew Ng",
        "watch_person": "Andrew Ng",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "leader_activity_signal": True,
        "leader_priority": 10,
    }
    protected, regular = _eligibility_split([item], max_protected=2)
    assert len(protected) == 1
    assert regular == []
    assert protected[0]["leader_activity_signal"] is True
    assert protected[0]["protected_content"] is True
    assert protected[0]["protected_reason"] == "leader_activity"
    assert protected[0]["_rank_is_tier0"] is True


def test_substantive_leader_interview_remains_protected():
    item = {
        "title": "Andrew Ng in a substantive interview on AI research",
        "content_type": "interview",
        "summary": "A long-form interview covering AI research, education, agents, evaluation and deployment with substantial context.",
        "leader": "Andrew Ng",
        "watch_person": "Andrew Ng",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_named_leader_interview": True,
        "leader_priority": 10,
    }
    protected, regular = _eligibility_split([item], max_protected=2)
    assert len(protected) == 1
    assert regular == []
    assert protected[0]["protected_content"] is True
    assert protected[0]["protected_reason"] == "leader_interview"
