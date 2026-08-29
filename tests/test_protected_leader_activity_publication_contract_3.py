from src.priority_people import is_substantive_priority_interview


def test_protected_leader_activity_is_tier0_for_publication():
    item = {
        "title": "SSI Product-Before-ASI Odds Hit 82% as Sutskever's Lab Hints at First Model",
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
        "normal_period_rank": None,
    }
    assert is_substantive_priority_interview(item) is True
