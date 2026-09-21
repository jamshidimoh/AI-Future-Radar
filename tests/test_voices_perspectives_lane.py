from src import publication_guard
from src.voices_perspectives_lane import MAX_VOICES_PER_PERIOD, choose_voices_candidate, is_voices_candidate


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
    no_person = _voice(); no_person.pop("person_name")
    assert not is_voices_candidate(no_person)


def test_voice_lane_accepts_watched_person_news_without_interview_keyword():
    item = {
        "title": "Sam Altman says frontier AI development needs stronger safety measures",
        "summary": "OpenAI CEO Sam Altman discussed artificial intelligence safety and the pace of frontier model development.",
        "mission_area": "ai", "category": "ai", "content_type": "news",
        "source": "Specialist publication", "source_type": "specialist", "source_tier": 1,
        "published": "2026-09-16T10:00:00+00:00", "watch_person": "Sam Altman",
        "is_leader_watch": True, "leader_priority": 10,
    }
    assert is_voices_candidate(item)


def test_voice_lane_allows_substantive_priority_interview_marked_tier0():
    item = _voice("David Chalmers interview on AI consciousness")
    item.update({"watch_person": "David Chalmers", "is_leader_watch": True, "leader_priority": 9, "_rank_is_tier0": True})
    assert is_voices_candidate(item)


def test_voice_lane_rejects_excluded_sources():
    for source in ("Reddit", "community forum", "aggregator", "arXiv"):
        item = _voice(); item["source"] = source
        assert not is_voices_candidate(item)


def test_voice_lane_skips_published_story_and_keeps_next_candidate(monkeypatch):
    def fake_guard(text, source_link="", records=None):
        return (False, "semantic_story_already_published score=1.000") if "Already Published" in text else (True, "no_publication_conflict")
    monkeypatch.setattr(publication_guard, "check_before_publish", fake_guard)
    first = _voice("Already Published interview")
    second = _voice("New Dario Amodei interview"); second["person_name"] = "Dario Amodei"
    selected = choose_voices_candidate([first, second])
    assert len(selected) == 1 and selected[0]["title"] == "New Dario Amodei interview"


def test_voice_lane_title_only_prefilter_blocks_missing_summary_duplicate(monkeypatch):
    calls = []
    def fake_guard(text, source_link="", records=None):
        calls.append(text)
        if "Already Published Voice" in text:
            return False, "semantic_story_already_published score=0.900"
        return True, "no_publication_conflict"
    monkeypatch.setattr(publication_guard, "check_before_publish", fake_guard)
    duplicate = _voice("Already Published Voice"); duplicate.pop("summary")
    replacement = _voice("Fresh David Chalmers interview"); replacement["person_name"] = "David Chalmers"
    selected = choose_voices_candidate([duplicate, replacement])
    assert selected and selected[0]["title"] == "Fresh David Chalmers interview"
    assert any("Already Published Voice" in text and "خلاصه:" in text for text in calls)


def test_voice_lane_freshness_selects_newer_watched_expert_without_person_priority_bias(monkeypatch):
    monkeypatch.setattr(publication_guard, "check_before_publish", lambda *args, **kwargs: (True, "no_publication_conflict"))
    older = _voice("UNIQUE-VOICE-FRESHNESS expert perspective A frontier AI")
    older.update({
        "watch_person": "Expert A",
        "leader": "Expert A",
        "person_name": "Expert A",
        "leader_priority": 100,
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "published": "2026-08-20T10:00:00+00:00",
    })
    newer = _voice("UNIQUE-VOICE-FRESHNESS expert perspective B frontier AI")
    newer.update({
        "watch_person": "Expert B",
        "leader": "Expert B",
        "person_name": "Expert B",
        "leader_priority": 1,
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "published": "2026-09-21T10:00:00+00:00",
    })
    selected = choose_voices_candidate([older, newer])
    assert selected and selected[0]["watch_person"] == "Andrew Ng"


def test_voice_lane_is_independent_and_capped_at_one():
    items = [_voice("Interview A"), _voice("Interview B")]
    selected = choose_voices_candidate(items)
    assert len(selected) == MAX_VOICES_PER_PERIOD == 1
    assert selected[0]["editorial_lane"] == "voices_perspectives"
    assert selected[0]["normal_period_rank"] is None
    assert selected[0]["mind_period_rank"] is None

    

def test_voice_lane_uses_expert_registry_for_registered_podcast():
    item = {
        "title": "Dwarkesh Podcast: frontier AI conversation",
        "summary": "A substantive discussion of frontier AI research, scaling, and reasoning.",
        "mission_area": "ai_core",
        "content_type": "podcast",
        "source": "YouTube - Dwarkesh Patel",
        "source_name": "Dwarkesh Patel",
        "source_type": "podcast",
        "source_tier": 1,
        "published": "2026-09-20T10:00:00+00:00",
    }
    assert is_voices_candidate(item)
    selected = choose_voices_candidate([item])
    assert selected and selected[0]["voice_identity_people"] == ["Dwarkesh Patel"]
    assert selected[0]["voice_expert_deep_lane"] is True


def test_voice_lane_does_not_promote_unnamed_event_stream_to_expert_voice():
    item = _voice("Annual Meetings of the Global Future Councils and Cybersecurity")
    item.pop("person_name")
    item["source"] = "YouTube - World Economic Forum"
    item["source_name"] = "World Economic Forum"
    item["content_type"] = "talk"
    assert not is_voices_candidate(item)


def test_voice_lane_preserves_registered_expert_identity_when_type_is_leader_signal():
    item = {
        "title": "Sam Altman discusses frontier AI",
        "summary": "A substantive discussion of frontier AI, agents, and model development.",
        "mission_area": "ai_core",
        "content_type": "leader_signal",
        "source": "Google News",
        "source_type": "news_aggregator",
        "source_tier": 1,
        "watch_person": "Sam Altman",
        "leader": "Sam Altman",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "leader_priority": 10,
        "leader_signal_classification": {"accepted": True, "interview": True, "context": True},
    }
    selected = choose_voices_candidate([item])
    assert selected
    assert "Sam Altman" in selected[0]["voice_identity_people"]


