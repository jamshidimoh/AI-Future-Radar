from period_ranked_pipeline import _global_ranked_selection


def test_global_ranked_selection_assigns_normal_period_rank():
    items = [
        {"title": "normal story A", "score": 120, "link": "https://example.com/a"},
        {"title": "normal story B", "score": 110, "link": "https://example.com/b"},
    ]

    ranked = _global_ranked_selection(
        items,
        max_posts=3,
        max_per_source=10,
        max_per_type=10,
        policy={},
    )

    assert len(ranked) == 2
    assert [item["normal_period_rank"] for item in ranked] == [1, 2]
    assert all(item["period_rank"] is not None for item in ranked)


def test_production_adapter_exports_only_the_canonical_selector():
    import period_ranked_pipeline as adapter

    # The production entrypoint still resolves its selector through the
    # adapter, so the exported symbol must be the canonical period ranker,
    # never the legacy selector imported from main.
    assert adapter.select_editorial is adapter._global_ranked_selection
    assert "_split_protected" not in adapter.__dict__
