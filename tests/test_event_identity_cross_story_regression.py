from src.event_identity import compare_events


def test_shared_announcement_language_does_not_make_different_entities_duplicates():
    first = {
        "title": "GPT-6 Astra is introduced with new reasoning capabilities",
        "summary": "OpenAI introduced GPT-6 Astra with a new reasoning architecture and evaluation results.",
    }
    second = {
        "title": "Google announces Gemini Ultra 4 for enterprise workloads",
        "summary": "Google announced Gemini Ultra 4 with enterprise capabilities and updated benchmarks.",
    }
    kind, _, evidence = compare_events(first, second)
    assert kind != "DUPLICATE", evidence


def test_same_entity_and_same_event_remains_duplicate():
    first = {
        "title": "Meta launches Muse agent",
        "summary": "Meta launched Muse, an agent for interactive tasks.",
    }
    second = {
        "title": "Meta introduces Muse agent for interactive tasks",
        "summary": "Meta introduced Muse as an agent for interactive tasks.",
    }
    assert compare_events(first, second)[0] == "DUPLICATE"
