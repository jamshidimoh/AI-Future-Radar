import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_models import SourceItem
from story_engine import build_stories


class StoryEngineTests(unittest.TestCase):
    def item(self, title, url, summary="", source_type="news"):
        return SourceItem(
            source_id="test",
            source_name="Test",
            url=url,
            title=title,
            summary=summary,
            source_type=source_type,
            published_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        )

    def test_empty_input_returns_no_stories(self):
        self.assertEqual(build_stories([]), [])

    def test_same_url_becomes_one_story(self):
        items = [
            self.item("OpenAI releases new model", "https://example.com/a"),
            self.item("OpenAI releases new model", "https://example.com/a"),
        ]
        stories = build_stories(items)
        self.assertEqual(len(stories), 1)
        self.assertEqual(len(stories[0].sources), 2)

    def test_different_topics_do_not_cluster(self):
        items = [
            self.item("OpenAI releases a new model", "https://a.example/1", "new model launch"),
            self.item("Quantum processor reaches new benchmark", "https://b.example/2", "quantum hardware benchmark"),
        ]
        stories = build_stories(items)
        self.assertEqual(len(stories), 2)

    def test_similar_cross_source_items_cluster(self):
        items = [
            self.item("OpenAI launches a new reasoning model", "https://a.example/1", "new reasoning model available"),
            self.item("OpenAI launches new reasoning model", "https://b.example/2", "reasoning model launch available"),
        ]
        stories = build_stories(items, similarity_threshold=0.55)
        self.assertEqual(len(stories), 1)
        self.assertEqual(len(stories[0].sources), 2)

    def test_story_contains_people_and_organizations(self):
        first = self.item("Andrew Ng joins AI venture", "https://a.example/1")
        first.people = ["Andrew Ng"]
        first.organizations = ["Coursera"]
        second = self.item("Andrew Ng launches AI venture", "https://b.example/2", "launch details")
        second.people = ["Andrew Ng"]
        second.organizations = ["Coursera"]
        stories = build_stories([first, second], similarity_threshold=0.4)
        self.assertEqual(stories[0].people, ["Andrew Ng"])
        self.assertEqual(stories[0].organizations, ["Coursera"])


if __name__ == "__main__":
    unittest.main()
