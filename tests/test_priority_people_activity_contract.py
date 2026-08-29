from src.priority_people import is_substantive_priority_interview, priority_people_features


def test_protected_leader_activity_reuses_ranked_tier_zero_contract():
    item = {
        "title": "SSI product-before-ASI odds hit 82% as Sutskever's lab hints at first model",
        "content_type": "news",
        "summary": "A substantive report about Ilya Sutskever's lab and a model-development milestone.",
        "leader": "ilya sutskever",
        "watch_person": "ilya sutskever",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "leader_activity_signal": True,
        "protected_content": True,
        "protected_reason": "leader_activity",
        "_rank_is_tier0": True,
    }
    people, tier0, bonus = priority_people_features(item)
    assert people == ["ilya sutskever"]
    assert tier0 is True
    assert bonus == 50.0
    assert is_substantive_priority_interview(item) is True


def test_unprotected_normal_leader_news_remains_normal():
    item = {
        "title": "Ilya Sutskever appears in a market report",
        "content_type": "news",
        "summary": "A short market report mentions Ilya Sutskever.",
        "leader": "ilya sutskever",
    }
    assert is_substantive_priority_interview(item) is False
