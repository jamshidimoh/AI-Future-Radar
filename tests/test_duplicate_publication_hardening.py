from story_identity import deduplicate_stories


def test_cross_source_same_event_with_different_urls_is_removed():
    prior = {
        "title": "OpenAI launches new AI agents for developers",
        "summary": "OpenAI announced a new generation of AI agents for developers.",
        "link": "https://source-one.example/openai-agents",
    }
    candidate = {
        "title": "OpenAI unveils AI agents aimed at developers",
        "summary": "The company introduced new AI agents designed for developers.",
        "link": "https://source-two.example/openai-ai-agents",
    }
    assert deduplicate_stories([candidate], history=[prior]) == []


def test_material_update_with_changed_numbers_is_not_suppressed():
    prior = {
        "title": "OpenAI reports 10 million AI agent users",
        "summary": "OpenAI shared adoption figures for its AI agents.",
        "link": "https://source-one.example/report",
    }
    candidate = {
        "title": "OpenAI reports 20 million AI agent users",
        "summary": "OpenAI shared updated adoption figures for its AI agents.",
        "link": "https://source-two.example/report-update",
    }
    assert deduplicate_stories([candidate], history=[prior]) == [candidate]


def test_exact_same_url_is_always_removed():
    prior = {"title": "New AI model released", "link": "https://example.com/story?id=42"}
    candidate = {"title": "Different headline for same story", "link": "https://example.com/story?id=42"}
    assert deduplicate_stories([candidate], history=[prior]) == []
