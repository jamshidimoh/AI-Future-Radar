import period_ranked_pipeline


def test_production_selector_is_canonical_period_ranker():
    assert period_ranked_pipeline.select_editorial is period_ranked_pipeline._global_ranked_selection


def test_period_ranker_assigns_normal_rank_to_normal_candidates():
    items = [
        {"title": "normal story", "editorial_score": 100, "signal_score": 1},
        {"title": "second story", "editorial_score": 90, "signal_score": 1},
    ]
    ranked = period_ranked_pipeline._global_ranked_selection(items, 3, 10, 10, None)
    normal = [item for item in ranked if not item.get("_rank_is_tier0")]
    assert normal
    assert all(item.get("normal_period_rank") is not None for item in normal)
