from story_gate import gate_story_candidates


def test_gate_preserves_protected_priority_across_all_candidate_pools():
    history = []
    protected = [
        {"title": "OpenAI launches new reasoning model", "protected_content": True, "leader_priority": 10}
    ]
    leader = [
        {"title": "OpenAI launches a new reasoning model", "leader_priority": 5}
    ]
    regular = [
        {"title": "OpenAI introduces its new reasoning model", "editorial_score": 9}
    ]

    result = gate_story_candidates(protected, leader, regular, history, threshold=0.45)

    assert len(result) == 1
    assert result[0]["protected_content"] is True


def test_gate_blocks_history_before_any_pool_can_reintroduce_story():
    from semantic_dedup import get_story_signature

    history = [get_story_signature({"title": "NVIDIA unveils next generation accelerator"})]
    protected = [{"title": "NVIDIA unveils next-generation accelerator", "protected_content": True}]
    leader = [{"title": "NVIDIA introduces next generation accelerator"}]
    regular = [{"title": "Another unrelated technology story"}]

    result = gate_story_candidates(protected, leader, regular, history, threshold=0.45)

    assert len(result) == 1
    assert result[0]["title"] == "Another unrelated technology story"
