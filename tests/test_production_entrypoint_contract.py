from production_entrypoint import normal_news_policy_allowed
from src.priority_people import is_substantive_priority_interview


def test_leader_activity_protected_story_is_not_forced_into_normal_rank_window():
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
    assert not is_substantive_priority_interview(item)
    assert item["_rank_is_tier0"] is True
    assert item["normal_period_rank"] is None


def test_normal_story_still_requires_normal_rank():
    assert not normal_news_policy_allowed(70.0, 55.75, None)
    assert normal_news_policy_allowed(70.0, 55.75, 1)
