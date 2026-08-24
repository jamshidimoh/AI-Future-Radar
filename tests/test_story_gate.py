from story_gate import gate_story_candidates


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
