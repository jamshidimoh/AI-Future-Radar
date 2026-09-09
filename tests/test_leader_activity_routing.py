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


def test_generic_leader_statement_is_not_tier_zero_activity():
    item = {
        "title": "Ashley St. Clair says she rejected a large NDA",
        "content_type": "news",
        "summary": "A personal dispute report about a proposed agreement, with no substantive AI technology development.",
        "leader": "Ashley St. Clair",
        "watch_person": "Ashley St. Clair",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "leader_activity_signal": True,
        "leader_priority": 10,
    }
    protected, regular = _eligibility_split([item], max_protected=2)
    assert protected == []
    assert len(regular) == 1
    assert regular[0]["protected_content"] is False
    assert regular[0]["_rank_is_tier0"] is False


def test_leader_launch_without_ai_context_is_not_tier_zero():
    item = {
        "title": "Mark Zuckerberg returned to X after launching a rival platform",
        "content_type": "news",
        "summary": "A social-media platform story focused on an executive's return to another platform.",
        "leader": "Mark Zuckerberg",
        "watch_person": "Mark Zuckerberg",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "leader_activity_signal": True,
        "leader_priority": 10,
    }
    protected, regular = _eligibility_split([item], max_protected=2)
    assert protected == []
    assert len(regular) == 1
    assert regular[0]["protected_content"] is False
    assert regular[0]["_rank_is_tier0"] is False
