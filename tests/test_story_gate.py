from editorial_score_v2 import score_editorial_v2
from story_gate import gate_story_candidates, story_representative_rank_key
from technology_signal_v2 import calculate_technology_signal_score


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


def test_story_gate_sets_p3_canonical_final_score():
    item = {
        "title": "Standalone AI story",
        "_ai_link": True,
        "mission_area": "ai_core",
        "source_tier": 1,
        "evidence_text": "primary evidence",
        "research_signal": True,
        "content_type": "research",
        "freshness_hours": 12,
        "signal_vector": {"novelty": 10, "future_impact": 8, "technical_significance": 9, "strategic_relevance": 7, "trend_alignment": 6},
    }
    result = gate_story_candidates([], [], [item], [])
    editorial, _ = score_editorial_v2(result[0])
    signal = calculate_technology_signal_score(item["signal_vector"])
    assert len(result) == 1
    assert result[0]["editorial_score_pre_signal"] == editorial
    assert result[0]["technology_signal_score"] == signal
    assert result[0]["final_editorial_score"] == round(0.75 * editorial + 0.25 * signal, 2)
    assert result[0]["story_representative_score"] == editorial
