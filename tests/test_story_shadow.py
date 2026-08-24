import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from story_shadow import build_shadow_stories


class StoryShadowTests(unittest.TestCase):
    def test_shadow_groups_cross_source_story(self):
        items = [
            {"source": "A", "link": "https://a.example/1", "title": "OpenAI launches a new reasoning model", "summary": "new reasoning model available", "published": "2026-08-19T08:00:00+00:00"},
            {"source": "B", "link": "https://b.example/2", "title": "OpenAI launches new reasoning model", "summary": "reasoning model launch available", "published": "2026-08-19T08:05:00+00:00"},
        ]
        stories, telemetry = build_shadow_stories(items, similarity_threshold=0.55)
        self.assertEqual(len(stories), 1)
        self.assertEqual(len(stories[0].sources), 2)
        self.assertEqual(telemetry["input_items"], 2)
        self.assertEqual(telemetry["shadow_stories"], 1)

    def test_shadow_keeps_different_topics_separate(self):
        items = [
            {"source": "A", "link": "https://a.example/1", "title": "OpenAI releases a new model", "summary": "new model launch"},
            {"source": "B", "link": "https://b.example/2", "title": "Quantum processor reaches new benchmark", "summary": "quantum hardware benchmark"},
        ]
        stories, _ = build_shadow_stories(items)
        self.assertEqual(len(stories), 2)

    def test_shadow_preserves_leader_identity(self):
        items = [
            {"source": "A", "link": "https://a.example/1", "title": "Interview with Dario Amodei", "leader": "Dario Amodei"},
        ]
        stories, _ = build_shadow_stories(items)
        self.assertEqual(stories[0].people, ["Dario Amodei"])

    def test_shadow_normalizes_mixed_timestamps_and_people(self):
        items = [
            {
                "source": "A",
                "link": "https://a.example/1",
                "title": "AI research update",
                "published": "2026-08-19T08:00:00+00:00",
                "people": ["Dario Amodei", "Research Lead"],
                "organizations": "Anthropic",
                "topics": "AI safety",
            },
            {
                "source": "B",
                "link": "https://b.example/2",
                "title": "AI research update",
                "published": "2026-08-19T09:00:00",
            },
            {
                "source": "C",
                "link": "https://c.example/3",
                "title": "AI research update",
            },
        ]
        stories, _ = build_shadow_stories(items, similarity_threshold=0.55)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0].people, ["Dario Amodei", "Research Lead"])
        self.assertEqual(stories[0].organizations, ["Anthropic"])
        self.assertEqual(stories[0].topics, ["AI safety"])


if __name__ == "__main__":
    unittest.main()
