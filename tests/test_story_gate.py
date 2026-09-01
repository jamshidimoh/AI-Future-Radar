from story_gate import gate_story_candidates, story_representative_rank_key


def test_cross_pool_duplicate_is_removed_once():
    history = []
    protected = [{"title": "OpenAI launches new reasoning model", "protected_content": True, "leader_priority": 10}]
    leader = [{"title": "OpenAI launches a new reasoning model", "leader_priority": 5}]
    regular = [{"title": "OpenAI introduces its new reasoning model", "editorial_score": 9}]
    result = gate_story_candidates(protected, leader, regular, history, threshold=0.45)
    assert len(result) == 1
    assert result[0]["protected_content"] is True


def test_history_is_shared_across_all_pools():
    history_item = {"title": "NVIDIA unveils next generation accelerator"}
    protected = [{"title": "NVIDIA unveils next-generation accelerator", "protected_content": True}]
    leader = [{"title": "Completely unrelated AI interview"}]
    regular = [{"title": "Another unrelated technology story"}]
    from semantic_dedup import get_story_signature
    result = gate_story_candidates(protected, leader, regular, [get_story_signature(history_item)], threshold=0.45)
    assert all("NVIDIA" not in item["title"] for item in result)
    assert len(result) == 2


def test_production_gate_preserves_protected_priority_and_blocks_cross_pool_duplicate():
    protected = [{"title": "OpenAI launches new reasoning model", "protected_content": True, "leader_priority": 10}]
    leader = [{"title": "OpenAI launches a new reasoning model", "leader_priority": 5, "is_leader": True}]
    regular = [{"title": "OpenAI introduces its new reasoning model", "editorial_score": 9}]
    result = gate_story_candidates(protected, leader, regular, [], threshold=0.45)
    assert len(result) == 1
    assert result[0]["protected_content"] is True


def test_representative_rank_ignores_signal_inflation():
    left = {
        "title": "Same event from source A",
        "editorial_score_pre_signal": 80,
        "editorial_score": 110,
        "signal_score": 100,
        "published": "2026-09-01 10:00",
    }
    right = {
        "title": "Same event from source B",
        "editorial_score_pre_signal": 85,
        "editorial_score": 90,
        "signal_score": 10,
        "published": "2026-09-01 09:00",
    }
    assert story_representative_rank_key(left)[3] == 80
    assert story_representative_rank_key(right)[3] == 85
    assert story_representative_rank_key(right) > story_representative_rank_key(left)


def test_story_gate_sets_canonical_final_score_from_pre_signal_and_signal():
    result = gate_story_candidates(
        [],
        [],
        [{
            "title": "Standalone AI story",
            "editorial_score_pre_signal": 77.5,
            "editorial_score": 93.09,
            "signal_score": 51.95,
        }],
        [],
    )
    assert len(result) == 1
    assert result[0]["final_editorial_score"] == 71.11
    assert result[0]["story_representative_score"] == 77.5
