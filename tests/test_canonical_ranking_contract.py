import importlib


ranking = importlib.import_module("period_ranked_pipeline")


def test_canonical_rank_uses_pre_signal_editorial_once():
    item = {
        "editorial_score_pre_signal": 80,
        "editorial_score": 120,
        "signal_score": 40,
    }
    assert ranking.canonical_rank_score(item) == 70.0


def test_canonical_rank_does_not_use_person_or_model_bonus():
    base = {
        "editorial_score_pre_signal": 80,
        "signal_score": 40,
    }
    boosted_metadata = {
        **base,
        "priority_person_bonus_legacy": 50,
        "model_release_bonus_legacy": 32,
        "leader_priority": 100,
        "_rank_is_tier0": True,
    }
    assert ranking.canonical_rank_score(base) == ranking.canonical_rank_score(boosted_metadata)


def test_tier0_is_routing_metadata_not_score_bonus():
    normal = {
        "editorial_score_pre_signal": 80,
        "signal_score": 40,
        "_rank_is_tier0": False,
    }
    tier0 = {**normal, "_rank_is_tier0": True}
    assert ranking.canonical_rank_score(normal) == ranking.canonical_rank_score(tier0)


def test_score_function_reads_canonical_score_field_after_preparation():
    item = {"editorial_score_pre_signal": 80, "signal_score": 40}
    prepared = ranking._prepare_rank_features([item])[0]
    assert prepared["final_editorial_score"] == 70.0
    assert ranking._score(prepared) == 70.0
