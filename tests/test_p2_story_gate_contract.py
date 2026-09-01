from editorial_score_v2 import score_editorial_v2
from story_gate import gate_story_candidates, story_representative_rank_key
from technology_signal_v2 import calculate_technology_signal_score


def test_signal_does_not_change_representative_key():
    low_signal = {
        "leader_priority": 0,
        "leader_source_authority": 2,
        "protected_content": False,
        "editorial_score_pre_signal": 82.0,
        "editorial_score": 182.0,
        "signal_score": 100.0,
        "published": "2026-09-01 10:00",
    }
    high_pre_signal = {
        "leader_priority": 0,
        "leader_source_authority": 2,
        "protected_content": False,
        "editorial_score_pre_signal": 83.0,
        "editorial_score": 84.0,
        "signal_score": 1.0,
        "published": "2026-09-01 09:00",
    }
    assert story_representative_rank_key(high_pre_signal) > story_representative_rank_key(low_signal)


def test_gate_materializes_p3_canonical_final_score():
    item = {
        "title": "AI story",
        "_ai_link": True,
        "mission_area": "ai_core",
        "source_tier": 1,
        "evidence_text": "primary evidence",
        "research_signal": True,
        "content_type": "research",
        "freshness_hours": 12,
        "signal_vector": {"novelty": 8, "future_impact": 7, "technical_significance": 6, "strategic_relevance": 5, "trend_alignment": 4},
    }
    result = gate_story_candidates([], [], [item], [])
    editorial, _ = score_editorial_v2(result[0])
    signal = calculate_technology_signal_score(item["signal_vector"])
    assert result[0]["editorial_score_pre_signal"] == editorial
    assert result[0]["technology_signal_score"] == signal
    assert result[0]["final_editorial_score"] == round(0.75 * editorial + 0.25 * signal, 2)
