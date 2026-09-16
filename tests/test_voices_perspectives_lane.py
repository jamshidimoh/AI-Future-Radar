from src.voices_perspectives_lane import (
    MAX_VOICES_PER_PERIOD,
    choose_voices_candidate,
    is_voices_candidate,
)


def _voice(title="AI researcher interview"):
    return {
        "title": title,
        "summary": "A substantive interview about artificial intelligence and future research.",
        "mission_area": "ai_core",
        "content_type": "interview",
        "source": "Specialist publication",
        "source_type": "specialist",
        "source_tier": 1,
        "person_name": "AI Researcher",
        "published": "2026-09-16T10:00:00+00:00",
    }


def test_voice_candidate_requires_substantive_person_and_ai_signal():
    assert is_voices_candidate(_voice())
    no_person = _voice()
    no_person.pop("person_name")
    assert not is_voices_candidate(no_person)


def test_voice_lane_rejects_excluded_sources():
    for source in ("Reddit", "community forum", "aggregator", "arXiv"):
        item = _voice()
        item["source"] = source
        assert not is_voices_candidate(item)


def test_voice_lane_is_independent_and_capped_at_one():
    items = [_voice("Interview A"), _voice("Interview B")]
    selected = choose_voices_candidate(items)
    assert len(selected) == MAX_VOICES_PER_PERIOD == 1
    assert selected[0]["editorial_lane"] == "voices_perspectives"
    assert selected[0]["normal_period_rank"] is None
    assert selected[0]["mind_period_rank"] is None
    assert selected[0]["technical_trend_period_rank"] is None
