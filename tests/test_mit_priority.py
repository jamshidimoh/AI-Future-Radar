import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from editorial import select_editorial


class MITPriorityTests(unittest.TestCase):
    def test_authority_is_rank_signal_not_unconditional_override(self):
        items = [
            {
                "source": "Other Source",
                "title": "Other AI story",
                "editorial_score": 100,
                "signal_score": 10,
                "editorial_confidence": 0.8,
                "content_type": "research",
                "source_tier": 1,
                "research_signal": True,
                "category": "ai",
            },
            {
                "source": "MIT News",
                "title": "MIT researchers advance AI method",
                "editorial_score": 20,
                "signal_score": 10,
                "editorial_confidence": 0.8,
                "content_type": "research",
                "source_tier": 1,
                "research_signal": True,
                "category": "ai",
            },
        ]
        selected = select_editorial(items, max_posts=1, max_per_source=2, max_per_type=2, policy={"leader_interview_slots": 0})
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["source"], "Other Source")

    def test_leader_interview_outranks_authority_when_leader_slot_exists(self):
        items = [
            {
                "source": "Leader Podcast",
                "title": "Leader interview",
                "leader": "Test Leader",
                "watch_person": "Test Leader",
                "is_leader_watch": True,
                "leader_watch_protected": True,
                "content_type": "interview",
                "editorial_score": 100,
                "signal_score": 10,
                "editorial_confidence": 0.9,
                "category": "ai",
                "source_tier": 1,
            },
            {
                "source": "MIT News",
                "title": "MIT AI research",
                "content_type": "research",
                "research_signal": True,
                "editorial_score": 10,
                "signal_score": 10,
                "editorial_confidence": 0.8,
                "category": "ai",
                "source_tier": 1,
            },
        ]
        selected = select_editorial(items, max_posts=1, max_per_source=2, max_per_type=2, policy={"leader_interview_slots": 1})
        self.assertEqual(selected[0]["source"], "Leader Podcast")
        self.assertEqual(selected[0]["editorial_slot"], "leader_interview")


if __name__ == "__main__":
    unittest.main()
