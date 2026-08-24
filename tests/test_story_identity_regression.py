from story_gate import gate_story_candidates


def test_unrelated_ai_stories_are_not_duplicates():
    items = [
        {"title": "Why Superhuman AI Might Only Need to Master R&D - Ryan Greenblatt", "editorial_score": 81.16},
        {"title": "The question isn’t whether or not humans matter — it’s how will we make our impact count?", "editorial_score": 81.06},
        {"title": "AI in Context, produced by 80,000 Hours", "editorial_score": 77.46},
        {"title": "Build a modern LLM from scratch. Every line commented.", "editorial_score": 64.46},
    ]
    result = gate_story_candidates([], [], items, [], threshold=0.45)
    assert len(result) == 4


def test_same_story_rewrites_are_deduplicated():
    protected = [{"title": "OpenAI launches new reasoning model", "protected_content": True, "leader_priority": 10}]
    regular = [{"title": "OpenAI launches a new reasoning model", "editorial_score": 9}]
    result = gate_story_candidates(protected, [], regular, [], threshold=0.45)
    assert len(result) == 1
    assert result[0]["protected_content"] is True


def test_shared_company_and_event_are_not_enough_for_duplicate():
    items = [
        {"title": "NVIDIA releases a new accelerator for AI inference"},
        {"title": "NVIDIA announces a research partnership on robotics"},
    ]
    result = gate_story_candidates([], [], items, [], threshold=0.45)
    assert len(result) == 2


def test_history_duplicate_is_removed_without_blocking_unrelated_story():
    from semantic_dedup import get_story_signature
    history = [get_story_signature({"title": "NVIDIA unveils next generation accelerator"})]
    items = [
        {"title": "NVIDIA unveils next-generation accelerator"},
        {"title": "NVIDIA researchers discuss robotics and embodied AI"},
    ]
    result = gate_story_candidates([], [], items, history, threshold=0.45)
    assert len(result) == 1
    assert "robotics" in result[0]["title"].lower()
