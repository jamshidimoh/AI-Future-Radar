from src.event_identity import compare_events
from src.story_identity import is_story_duplicate


def test_same_person_different_events_are_distinct():
    previous = {
        "title": "Zuckerberg launches personal superintelligence plan",
        "summary": "Meta introduces the Muse agent and a new personal AI strategy.",
    }
    current = {
        "title": "Zuckerberg appoints a new Meta AI research chief",
        "summary": "Meta names a research leader to oversee frontier AI work.",
    }
    assert compare_events(previous, current)[0] != "DUPLICATE"
    assert is_story_duplicate(current, [previous]) is False


def test_same_company_different_events_are_distinct():
    previous = {
        "title": "OpenAI releases a new reasoning model",
        "summary": "The company publishes a new model with improved reasoning benchmarks.",
    }
    current = {
        "title": "OpenAI opens a new research center in Europe",
        "summary": "The company announces a new research hub and hiring program.",
    }
    assert compare_events(previous, current)[0] != "DUPLICATE"
    assert is_story_duplicate(current, [previous]) is False


def test_same_product_family_different_events_are_distinct():
    previous = {
        "title": "Meta introduces Muse agent for creative work",
        "summary": "Meta launches the Muse agent as a new AI product.",
    }
    current = {
        "title": "Meta reports new research findings about Muse training",
        "summary": "Researchers publish new findings about how the agent was trained.",
    }
    assert is_story_duplicate(current, [previous]) is False
