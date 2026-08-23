from src.priority_people import TOP_AI_VOICES, is_substantive_priority_interview, priority_people_bonus, matched_priority_people, priority_people_features


def test_exactly_twenty_unique_priority_voices():
    assert len(TOP_AI_VOICES) == 20


def test_substantive_interview_gets_tier_zero_priority():
    item = {
        "title": "Sam Altman in a long interview about AGI",
        "content_type": "podcast",
        "summary": "Sam Altman discusses model progress, agents, safety, deployment and the future of AI in a detailed conversation with substantial technical and strategic context.",
        "source": "AI podcast",
    }
    assert is_substantive_priority_interview(item)
    assert priority_people_bonus(item) > 0


def test_attributable_quote_from_priority_voice_gets_priority():
    item = {
        "title": "Eric Schmidt says AI capability is accelerating",
        "content_type": "news",
        "summary": "Eric Schmidt discussed model capability, infrastructure and strategic consequences in a substantive report with direct attribution and sufficient context for an editorial quote.",
        "key_quote": "AI capability is accelerating faster than expected.",
        "source": "technology interview report",
    }
    assert is_substantive_priority_interview(item)


def test_generic_news_about_priority_person_is_not_automatically_priority():
    item = {
        "title": "Elon Musk company stock rises",
        "content_type": "news",
        "summary": "A short market update about the company.",
        "source": "market news",
    }
    assert not is_substantive_priority_interview(item)


def test_generic_attribution_phrase_does_not_create_quote_priority():
    item = {
        "title": "Report cites Sam Altman among many executives",
        "content_type": "news",
        "summary": "A long industry report discusses many companies and executives but contains no direct quote, interview, or attributable statement from Sam Altman.",
        "source": "industry report",
    }
    assert not is_substantive_priority_interview(item)


def test_hassabis_alias_is_detected_in_interview_context():
    item = {
        "title": "Hassabis discusses the next generation of AI",
        "content_type": "interview",
        "summary": "A substantive conversation covers model capability, agents, scientific discovery, safety, and the strategic direction of AI research.",
    }
    assert matched_priority_people(item) == ["demis hassabis"]
    assert is_substantive_priority_interview(item)


def test_large_description_is_bounded_and_still_detects_person():
    item = {
        "title": "Sam Altman interview on AGI",
        "content_type": "interview",
        "description": "Sam Altman " + ("x" * 200000),
    }
    people, tier0, bonus = priority_people_features(item)
    assert "sam altman" in people
    assert tier0 is True
    assert bonus == 50.0


def test_configured_watchlist_person_outside_static_priority_list_gets_priority():
    item = {
        "title": "David Chalmers in a substantive conversation about AI consciousness",
        "content_type": "conversation",
        "summary": "David Chalmers discusses machine consciousness, AI systems, cognitive science, the implications of increasingly capable models, and several concrete research questions in a long-form conversation.",
        "watch_person": "David Chalmers",
        "leader": "David Chalmers",
        "is_leader_watch": True,
    }
    people, tier0, bonus = priority_people_features(item)
    assert people == ["david chalmers"]
    assert tier0 is True
    assert bonus == 50.0


def test_watchlist_metadata_does_not_make_short_news_item_tier_zero():
    item = {
        "title": "David Chalmers attends AI event",
        "content_type": "news",
        "summary": "A short event note.",
        "watch_person": "David Chalmers",
        "leader": "David Chalmers",
        "is_leader_watch": True,
    }
    assert not is_substantive_priority_interview(item)
