from story_gate import gate_story_candidates, story_representative_rank_key


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


def test_gate_materializes_canonical_final_score():
    result = gate_story_candidates([], [], [{
        "title": "AI story",
        "editorial_score_pre_signal": 77.5,
        "editorial_score": 93.09,
        "signal_score": 51.95,
    }], [])
    assert result[0]["final_editorial_score"] == 71.11
    assert result[0]["story_representative_score"] == 77.5
