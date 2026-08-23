import period_ranked_pipeline as ranking


def test_canonical_rank_combines_editorial_and_signal_once():
    item = {
        "editorial_score_pre_signal": 80.0,
        "editorial_score": 104.0,  # legacy main.py mutation must not matter
        "signal_score": 60.0,
        "model_release_bonus": 32.0,
        "priority_person_bonus": 50.0,
    }
    assert ranking.canonical_rank_score(item) == 75.0


def test_prepare_features_does_not_add_person_or_model_bonus_to_final_score(monkeypatch):
    monkeypatch.setattr(ranking, "model_release_bonus", lambda item: 32.0)
    monkeypatch.setattr(ranking, "priority_people_features", lambda item: (["Sam Altman"], True, 50.0))
    item = {
        "title": "A substantive technology claim",
        "editorial_score_pre_signal": 80.0,
        "editorial_score": 104.0,
        "signal_score": 60.0,
        "leader": "Sam Altman",
    }
    ranking._prepare_rank_features([item])
    assert item["model_release_priority"] is True
    assert item["priority_person_interview"] is True
    assert item["model_release_bonus_legacy"] == 32.0
    assert item["priority_person_bonus_legacy"] == 50.0
    assert item["final_editorial_score"] == 75.0


def test_tier0_remains_policy_routing_not_score_inflation(monkeypatch):
    monkeypatch.setattr(ranking, "model_release_bonus", lambda item: 0.0)
    monkeypatch.setattr(ranking, "priority_people_features", lambda item: (["Sam Altman"], True, 50.0))
    item = {
        "title": "Sam Altman discusses future AI systems",
        "editorial_score_pre_signal": 55.0,
        "signal_score": 40.0,
        "leader": "Sam Altman",
        "content_type": "interview",
        "_named_leader_interview": True,
    }
    ranking._prepare_rank_features([item])
    assert item["_rank_is_tier0"] is True
    assert item["final_editorial_score"] == 51.25
