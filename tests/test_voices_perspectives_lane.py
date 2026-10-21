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
        if "Already Published AI Voice" in text:
            return False, "semantic_story_already_published score=0.900"
        return True, "no_publication_conflict"
    monkeypatch.setattr(publication_guard, "check_before_publish", fake_guard)
    duplicate = _voice("Already Published AI Voice"); duplicate.pop("summary")
    replacement = _voice("Fresh David Chalmers interview"); replacement["person_name"] = "David Chalmers"
    selected = choose_voices_candidate([duplicate, replacement])
    assert selected and selected[0]["title"] == "Fresh David Chalmers interview"
    assert any("Already Published AI Voice" in text and "خلاصه:" in text for text in calls)


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
    assert selected and selected[0]["watch_person"] == "Expert B"


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




def test_voice_lane_prefers_newer_direct_interview_over_older_higher_tier():
    older = _voice("Older expert interview")
    older["published"] = "2026-09-18T10:00:00+00:00"
    older["source_tier"] = 1
    older["person_name"] = "David Chalmers"

    newer = _voice("Newer expert interview")
    newer["published"] = "2026-09-22T06:00:00+00:00"
    newer["source_tier"] = 3
    newer["person_name"] = "Anil Seth"

    selected = choose_voices_candidate([older, newer], max_items=1)
    assert selected and selected[0]["title"] == "Newer expert interview"


def test_voice_lane_does_not_trust_mislabelled_mission_area_without_topical_evidence():
    for mission_area in ("ai_core", "convergence", "mind_cognition"):
        item = _voice("Why horses terrified the Aztecs — Si Sheppard")
        item.update({
            "mission_area": mission_area,
            "category": "ai",
            "summary": "A historical account of horses and the Aztec empire.",
            "description": "A discussion of historical warfare and cultural change.",
            "person_name": "Si Sheppard",
            "content_type": "interview",
            "source_type": "specialist",
            "source_tier": 1,
        })
        assert not is_voices_candidate(item)


def test_voice_lane_accepts_topical_cognition_and_philosophy_without_ai_acronym():
    item = _voice("David Chalmers on philosophy of mind and consciousness")
    item.update({
        "mission_area": "mind_cognition",
        "summary": "A substantive conversation about consciousness, self-awareness and cognitive science.",
        "person_name": "David Chalmers",
    })
    assert is_voices_candidate(item)


def test_voice_lane_rejects_bare_ai_category_without_ai_evidence():
    item = _voice("Why are wildfires increasing?")
    item.pop("mission_area")
    item["category"] = "ai"
    item["summary"] = "A discussion of extreme heat, wind, dryness, and wildfire resilience."
    item["source"] = "World Economic Forum"
    item["source_name"] = "World Economic Forum"
    item["person_name"] = "Natalie Çilem"
    assert not is_voices_candidate(item)

def test_voice_lane_rejects_unrelated_leader_video_even_when_routing_flags_claim_ai():
    item = _voice("Why Russian Tsars lost control: an episode with Dwarkesh Patel")
    item.update({
        "summary": "A historical explanation of the Russian monarchy, political control, and imperial collapse.",
        "description": "Discussion of early modern Russian history, court politics, and war.",
        "evidence_text": "The episode analyzes the historical loss of control by Russian Tsars.",
        "mission_area": "ai_core",
        "category": "ai",
        "content_type": "interview",
        "source": "YouTube - Dwarkesh Patel",
        "source_name": "Dwarkesh Patel",
        "source_type": "podcast",
        "source_tier": 1,
        "watch_person": "Dwarkesh Patel",
        "leader": "Dwarkesh Patel",
        "person_name": "Dwarkesh Patel",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "protected_content": True,
        "_ai_link": True,
        "ai_relevance": True,
    })
    assert not is_voices_candidate(item)


def test_voice_lane_accepts_interview_when_source_evidence_contains_topic_anchor():
    item = _voice("Long-form interview with Sam Altman")
    item.update({
        "summary": "A long-form conversation about recent research directions.",
        "description": "",
        "evidence_text": "The speaker discusses frontier AI agents, model reasoning, and alignment.",
        "mission_area": "ai_core",
        "content_type": "interview",
        "source_type": "specialist",
        "source_tier": 1,
        "watch_person": "Sam Altman",
        "leader": "Sam Altman",
        "person_name": "Sam Altman",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_ai_link": True,
    })
    assert is_voices_candidate(item)

def test_voice_lane_accepts_direct_social_post_from_x_as_primary_attribution():
    item = {
        "title": "Sam Altman on X: frontier AI needs stronger evaluation",
        "summary": "The post discusses artificial intelligence evaluation and deployment risks.",
        "mission_area": "ai_core",
        "category": "ai",
        "content_type": "social_post",
        "source": "Google News (X)",
        "source_domain": "https://x.com/",
        "source_type": "news_aggregator",
        "source_tier": 3,
        "watch_person": "Sam Altman",
        "leader": "Sam Altman",
        "person_name": "Sam Altman",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "leader_signal_classification": {"accepted": True, "direct_post": True, "context": True},
    }
    assert is_voices_candidate(item)
    selected = choose_voices_candidate([item])
    assert selected and selected[0]["content_type"] == "social_post"


def test_voice_lane_does_not_treat_unverified_social_scrape_as_primary_source():
    item = {
        "title": "Sam Altman on X: frontier AI needs stronger evaluation",
        "summary": "The post discusses artificial intelligence evaluation and deployment risks.",
        "mission_area": "ai_core",
        "category": "ai",
        "content_type": "social_post",
        "source": "Unknown social scrape",
        "source_domain": "https://example.invalid/",
        "source_type": "news_aggregator",
        "source_tier": 3,
        "watch_person": "Sam Altman",
        "leader": "Sam Altman",
        "person_name": "Sam Altman",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "leader_signal_classification": {"accepted": True, "direct_post": True, "context": True},
    }
    assert not is_voices_candidate(item)

