import period_ranked_pipeline as ranking
from src.priority_people import priority_people_features


def test_canonical_rank_combines_editorial_and_signal_once():
    item = {"editorial_score_pre_signal": 80.0, "editorial_score": 104.0, "signal_score": 60.0, "model_release_bonus": 32.0, "priority_person_bonus": 50.0}
    assert ranking.canonical_rank_score(item) == 75.0


def test_prepare_features_does_not_add_person_or_model_bonus_to_final_score(monkeypatch):
    monkeypatch.setattr(ranking, "model_release_bonus", lambda item: 32.0)
    monkeypatch.setattr(ranking, "priority_people_features", lambda item: (["Sam Altman"], True, 50.0))
    item = {"title": "A substantive technology claim", "editorial_score_pre_signal": 80.0, "editorial_score": 104.0, "signal_score": 60.0, "leader": "Sam Altman"}
    ranking._prepare_rank_features([item])
    assert item["model_release_priority"] is True
    assert item["priority_person_interview"] is False
    assert item["model_release_bonus_legacy"] == 32.0
    assert item["priority_person_bonus_legacy"] == 0.0
    assert item["_rank_is_tier0"] is False
    assert item["final_editorial_score"] == 75.0


def test_tier0_remains_policy_routing_not_score_inflation(monkeypatch):
    monkeypatch.setattr(ranking, "model_release_bonus", lambda item: 0.0)
    monkeypatch.setattr(ranking, "priority_people_features", lambda item: (["Sam Altman"], True, 50.0))
    item = {"title": "Sam Altman discusses future AI systems", "editorial_score_pre_signal": 55.0, "signal_score": 40.0, "leader": "Sam Altman", "content_type": "interview", "_named_leader_interview": True, "protected_slot": True}
    ranking._prepare_rank_features([item])
    assert item["_rank_is_tier0"] is True
    assert item["final_editorial_score"] == 51.25


def test_unselected_priority_interview_does_not_silently_become_tier0(monkeypatch):
    monkeypatch.setattr(ranking, "model_release_bonus", lambda item: 0.0)
    monkeypatch.setattr(ranking, "priority_people_features", lambda item: (["Sam Altman"], True, 50.0))
    item = {"title": "Sam Altman discusses future AI systems", "editorial_score_pre_signal": 55.0, "signal_score": 40.0, "leader": "Sam Altman", "content_type": "interview"}
    ranking._prepare_rank_features([item])
    assert item["priority_person_interview"] is False
    assert item["_rank_is_tier0"] is False
    assert item["priority_person_bonus_legacy"] == 0.0


def test_ordinary_priority_person_quote_stays_out_of_tier0():
    item = {"title": "Five transactions in seven days put a price on AI agent governance", "summary": "Mark Zuckerberg said the market is changing rapidly and executives discussed AI agents.", "description": "A news report quotes Zuckerberg while covering several transactions.", "content_type": "news", "source": "StartupHub.ai", "key_quote": "The market is changing rapidly and companies must adapt."}
    people, is_tier0, bonus = priority_people_features(item)
    assert "mark zuckerberg" in people
    assert is_tier0 is False
    assert bonus == 0.0


def test_substantive_priority_interview_stays_tier0():
    item = {"title": "Mark Zuckerberg in conversation about the future of AI", "summary": "An extended interview explores Meta's AI strategy and the future of open models.", "description": "The conversation covers model development, agents, and long-term AI strategy.", "content_type": "interview", "source": "Podcast"}
    people, is_tier0, bonus = priority_people_features(item)
    assert "mark zuckerberg" in people
    assert is_tier0 is True
    assert bonus == 50.0


def test_protected_leader_capacity_demotes_overflow_candidates():
    items = [
        {"title": "Leader one", "leader": "Elon Musk", "editorial_score": 90.0, "content_type": "interview", "leader_watch_protected": True},
        {"title": "Leader two", "leader": "Sam Altman", "editorial_score": 89.0, "content_type": "interview", "leader_watch_protected": True},
        {"title": "Leader three", "leader": "Jensen Huang", "editorial_score": 88.0, "content_type": "interview", "leader_watch_protected": True},
    ]
    selected, regular = ranking._eligibility_split(items, max_protected=2)
    assert len(selected) == 2
    assert all(item.get("protected_slot") is True for item in selected)
    assert len(regular) == 1
    assert regular[0].get("protected_slot") is False
    assert regular[0].get("protected_content") is False
    assert regular[0].get("_rank_is_tier0") is False
