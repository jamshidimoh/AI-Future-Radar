from src.editorial import filter_ai_relevance


def test_leader_interview_without_ai_keyword_is_retained():
    items = [{
        "title": "Sam Altman on the future of computing",
        "summary": "A substantive interview with Sam Altman about computing and intelligence.",
        "content_type": "interview",
        "is_leader_watch": True,
        "leader": "Sam Altman",
        "source_tier": 1,
    }]
    result = filter_ai_relevance(items, ["AI"])
    assert len(result) == 1
    assert result[0]["early_inclusion_reason"] == "leader_interview"


def test_strategic_ai_policy_signal_is_retained():
    items = [{
        "title": "New AI regulation changes frontier-model governance",
        "summary": "The regulator announced a new policy for frontier models.",
        "content_type": "news",
        "source_tier": 1,
    }]
    result = filter_ai_relevance(items, ["AI"])
    assert len(result) == 1
    assert result[0]["early_inclusion_reason"] == "strategic_ai_or_tech"


def test_emerging_technology_from_authoritative_source_is_retained():
    items = [{
        "title": "New quantum computing processor reaches a major milestone",
        "summary": "Researchers report a new quantum processor architecture.",
        "content_type": "research",
        "source_tier": 1,
    }]
    result = filter_ai_relevance(items, ["AI"])
    assert len(result) == 1
    assert result[0]["early_inclusion_reason"] == "emerging_technology"


def test_unrelated_story_is_still_rejected():
    items = [{
        "title": "Local football club wins championship",
        "summary": "A sports result with no technology relevance.",
        "content_type": "news",
        "source_tier": 2,
    }]
    result = filter_ai_relevance(items, ["AI"])
    assert result == []
