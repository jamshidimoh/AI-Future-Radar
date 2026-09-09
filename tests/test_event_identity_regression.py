import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_identity import compare_events
from story_identity import deduplicate_stories, is_story_duplicate


def item(title, summary="", published="2026-09-09T00:00:00+00:00"):
    return {"title": title, "summary": summary, "published": published}


def test_muse_three_headlines_are_one_story():
    a = item("Zuckerberg launches personal superintelligence plan, Muse agent")
    b = item("Meta introduces Muse, a personal AI agent with dedicated cloud computer")
    c = item("Zuckerberg introduces personal superintelligence and Muse agent")
    assert compare_events(a, b)[0] == "DUPLICATE"
    assert compare_events(a, c)[0] == "DUPLICATE"
    assert is_story_duplicate(b, [a])
    assert is_story_duplicate(c, [a])


def test_terence_tao_two_headlines_are_one_story():
    a = item("Terence Tao: warning about AI threatening open science and unsolved math problems")
    b = item("Theoretical warning from Tao: risk of a shortage of open problems in the AI era")
    assert compare_events(a, b)[0] == "DUPLICATE"
    assert is_story_duplicate(b, [a])


def test_stanford_hai_two_headlines_are_one_story():
    a = item("AI legal review finds millions live under discriminatory local laws - Stanford HAI")
    b = item("AI-based legal review: millions of people live under discriminatory local laws")
    assert compare_events(a, b)[0] == "DUPLICATE"
    assert is_story_duplicate(b, [a])


def test_same_entities_different_event_is_not_duplicate():
    a = item("Meta introduces Muse personal AI agent")
    b = item("Meta reports a new security vulnerability in Muse")
    assert compare_events(a, b)[0] != "DUPLICATE"


def test_same_event_with_material_finding_is_not_duplicate():
    a = item("Meta introduces Muse personal AI agent")
    b = item("Meta reveals a newly discovered security vulnerability in Muse")
    assert compare_events(a, b)[0] == "UPDATE"


def test_different_events_same_person_are_not_duplicate():
    a = item("Zuckerberg launches personal superintelligence plan, Muse agent")
    b = item("Zuckerberg appoints a new Meta AI research chief")
    assert compare_events(a, b)[0] != "DUPLICATE"


def test_same_event_without_material_update_deduplicates_current_run():
    items = [
        item("Zuckerberg launches personal superintelligence plan, Muse agent"),
        item("Meta introduces Muse, a personal AI agent with dedicated cloud computer"),
        item("Zuckerberg introduces personal superintelligence and Muse agent"),
    ]
    assert len(deduplicate_stories(items)) == 1
