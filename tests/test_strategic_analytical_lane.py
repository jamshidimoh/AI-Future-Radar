from production_entrypoint import _is_strategic_analytical_signal, normal_news_policy_allowed
from src.source_authority import resolve_source_tier

HARARI_BASE = {
    "is_leader_watch": True,
    "leader": "Yuval Noah Harari",
    "leader_priority": 8,
    "category": "future",
    "content_type": "interview",
    "leader_signal_classification": {
        "accepted": True,
        "analytical": True,
        "context": True,
    },
}


def test_harari_strategic_analytical_signal_requires_trusted_source():
    item = {**HARARI_BASE, "source_tier": 2, "source": "The Economist", "source_name": "The Economist"}
    assert _is_strategic_analytical_signal(item) is True

    weak = {**HARARI_BASE, "source_tier": 3, "source": "finance.biggo.com", "source_name": "finance.biggo.com"}
    assert _is_strategic_analytical_signal(weak) is False


def test_strategic_lane_still_respects_leader_priority_and_mission_area():
    wrong_person = {**HARARI_BASE, "leader": "Low Priority Person", "leader_priority": 7, "source_tier": 2}
    assert _is_strategic_analytical_signal(wrong_person) is False

    ai_core = {**HARARI_BASE, "category": "ai", "source_tier": 2}
    assert _is_strategic_analytical_signal(ai_core) is False


def test_strategic_lane_does_not_change_normal_score_policy():
    assert normal_news_policy_allowed(44.45, 62.55, 5) is False


def test_economist_is_resolved_as_tier_two():
    assert resolve_source_tier(source_name="The Economist", source_url="https://www.economist.com/ai", configured_tier=3) == 2
