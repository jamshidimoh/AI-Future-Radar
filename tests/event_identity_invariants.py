import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_identity import classify_story, event_similarity


def test_known_rewrites_cluster_as_duplicates():
    pairs = [
        (
            {"title": "Zuckerberg introduces Personal Superintelligence and Muse"},
            {"title": "Introducing Muse by Meta; a personal AI agent with dedicated secure cloud computing"},
        ),
        (
            {"title": "Theoretical warning by Terence Tao: AI may exhaust open mathematical problems"},
            {"title": "Terence Tao: AI threatens the future of open science and mathematical problems"},
        ),
        (
            {"title": "AI legal review finds millions live under discriminatory local laws - Stanford HAI"},
            {"title": "AI-based legal review: millions of people live under discriminatory local laws"},
        ),
    ]
    for a, b in pairs:
        assert event_similarity(a, b) >= 0.78
        assert classify_story(b, a)[0] == "DUPLICATE"


def test_distinct_events_remain_distinct():
    pairs = [
        ({"title": "Meta introduces Muse personal AI agent"}, {"title": "Security vulnerability discovered in Muse"}),
        ({"title": "Meta introduces Muse"}, {"title": "Meta announces new AR glasses"}),
    ]
    for a, b in pairs:
        assert classify_story(b, a)[0] != "DUPLICATE"
