from src.unified_editorial_selection import is_mission_relevant, mission_area, select_regular_portfolio


def _item(title, summary=None, *, source="Nature", category="ai", content_type="news"):
    return {"title": title, "summary": summary or title, "source": source, "source_tier": 1, "category": category, "content_type": content_type, "_ai_link": True, "ai_relevance": True}


def test_low_signal_chatgpt_tutorial_is_rejected():
    item = _item("How to use ChatGPT to identify scam messages", source="YouTube - OpenAI")
    assert not is_mission_relevant(item, strict=True)


def test_energy_story_is_classified_as_convergence_before_legacy_ai_category():
    item = _item("Low-emission technologies reshape heavy industry", "Energy and industrial technologies are being commercialized to reduce emissions.", source="World Economic Forum")
    assert is_mission_relevant(item, strict=True)
    assert mission_area(item) == "convergence"


def test_known_aggregator_is_excluded_from_normal_mission_selection():
    item = _item("AI startup raises major funding", "A British AI startup is in advanced talks to raise hundreds of millions of dollars.", source="Techmeme")
    assert select_regular_portfolio([item], max_posts=1, max_per_source=1, max_per_type=1, recent_source_counts={}, mission_aware=True, strict_relevance=True) == []


def test_ai_consciousness_leader_signal_remains_mission_relevant():
    item = _item("Mustafa Suleyman discusses AI consciousness and Anthropic", "The Microsoft AI leader discusses machine consciousness, safety, and Anthropic.", source="Google News (Mashable)")
    assert is_mission_relevant(item, strict=True)
    assert mission_area(item) == "mind_cognition"
