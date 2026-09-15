from src.expert_registry import apply_expert_features, expert_features, load_expert_registry
from src.priority_people import priority_people_features


def test_registry_deduplicates_alias_identity():
    names = [item["name"] for item in load_expert_registry()]
    assert names.count("Chris Olah") == 1
    assert "Christopher Olah" not in names


def test_mind_expert_adds_bounded_signal_without_tier0_protection():
    item = {
        "title": "David Chalmers on AI consciousness and machine minds",
        "content_type": "interview",
        "speaker": "David Chalmers",
        "source": "Lex Fridman Podcast",
        "mission_area": "mind_cognition",
        "summary": "A substantive interview about consciousness, cognition, and AI minds.",
    }
    features = expert_features(item)
    assert "David Chalmers" in features["people"]
    assert "mind_cognition" in features["expert_domains"]
    assert features["expert_domain_relevant"] is True
    assert features["expert_deep_lane"] is True
    assert 0 < features["expert_bonus"] <= 8.0

    enriched = apply_expert_features(dict(item))
    assert enriched["_expert_signal_applied"] is True
    assert enriched["signal_score"] == features["expert_bonus"]
    assert enriched.get("protected_content") is not True


def test_expert_membership_never_grants_tier0():
    item = {
        "title": "A market report briefly mentions David Chalmers",
        "content_type": "news",
        "source": "Reuters",
        "mission_area": "future_governance",
        "summary": "A short market report with a passing reference to David Chalmers.",
    }
    features = expert_features(item)
    assert "David Chalmers" in features["people"]
    assert features["expert_deep_lane"] is False
    people, tier0, bonus = priority_people_features(item)
    assert people == []
    assert tier0 is False
    assert bonus == 0.0
    assert item.get("signal_score", 0.0) >= 0.0
