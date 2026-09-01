from story_gate import gate_story_candidates, story_representative_rank_key
from technology_signal_v2 import WEIGHTS as SIGNAL_WEIGHTS, calculate_technology_signal_score
from editorial_score_v2 import WEIGHTS as EDITORIAL_WEIGHTS, score_editorial_v2


def test_editorial_score_excludes_signal_features():
    item_a = {"_ai_link": True, "source_tier": 1, "evidence_text": "primary", "content_type": "research", "freshness_hours": 12, "signal_score": 10, "signal_vector": {"novelty": 1}}
    item_b = dict(item_a, signal_score=99, signal_vector={"novelty": 10, "future_impact": 10, "technical_significance": 10})
    assert score_editorial_v2(item_a)[0] == score_editorial_v2(item_b)[0]


def test_signal_score_excludes_editorial_source_and_freshness_dimensions():
    vector_a = {"novelty": 8, "future_impact": 7, "technical_significance": 6, "strategic_relevance": 5, "trend_alignment": 4, "freshness": 1, "source_quality": 1, "expert_influence": 1, "evidence_strength": 1}
    vector_b = dict(vector_a, freshness=10, source_quality=10, expert_influence=10, evidence_strength=10)
    assert calculate_technology_signal_score(vector_a) == calculate_technology_signal_score(vector_b)


def test_representative_is_invariant_to_signal_inflation():
    left = {"title": "Same event A", "editorial_score_pre_signal": 80, "editorial_score": 120, "signal_score": 100, "_ai_link": True, "source_tier": 2, "published": "2026-09-01 10:00"}
    right = {"title": "Same event B", "editorial_score_pre_signal": 85, "editorial_score": 90, "signal_score": 1, "_ai_link": True, "source_tier": 2, "published": "2026-09-01 09:00"}
    assert story_representative_rank_key(right)[3] > story_representative_rank_key(left)[3]


def test_weight_contracts_are_complete_and_sum_to_one():
    assert abs(sum(EDITORIAL_WEIGHTS.values()) - 1.0) < 1e-9
    assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9
    assert set(EDITORIAL_WEIGHTS) == {"mission_fit", "source_authority", "evidence_confidence", "publication_value", "freshness"}
    assert set(SIGNAL_WEIGHTS) == {"novelty", "future_impact", "technical_significance", "strategic_relevance", "trend_alignment"}


def test_gate_materializes_canonical_final_score_from_separated_scores():
    result = gate_story_candidates([], [], [{
        "title": "Research AI breakthrough",
        "_ai_link": True,
        "source_tier": 1,
        "evidence_text": "primary evidence",
        "research_signal": True,
        "content_type": "research",
        "freshness_hours": 12,
        "signal_vector": {"novelty": 10, "future_impact": 8, "technical_significance": 9, "strategic_relevance": 7, "trend_alignment": 6},
    }], [])
    assert len(result) == 1
    editorial, _ = score_editorial_v2(result[0])
    signal = calculate_technology_signal_score(result[0]["signal_vector"])
    assert result[0]["editorial_score_pre_signal"] == editorial
    assert result[0]["technology_signal_score"] == signal
    assert result[0]["final_editorial_score"] == round(0.75 * editorial + 0.25 * signal, 2)
