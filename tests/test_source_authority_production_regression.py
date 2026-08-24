import unittest

from src.mission_selector import _source_tier
from main import _split_protected


class SourceAuthorityProductionRegressionTests(unittest.TestCase):
    def test_low_authority_metadata_cannot_outrank_reputable_source(self):
        items = [
            {
                "title": "Dario Amodei interview on AI trust",
                "summary": "Dario Amodei discusses AI and public trust.",
                "leader": "Dario Amodei",
                "watch_person": "Dario Amodei",
                "content_type": "interview",
                "is_leader_watch": True,
                "leader_watch_protected": True,
                "leader_priority": 10,
                "source": "Google News (Bitcoin World)",
                "source_tier": 1,
                "published": "2026-08-17",
            },
            {
                "title": "Google leadership update involving Dario Amodei",
                "summary": "Reuters reports on an AI leadership development.",
                "leader": "Dario Amodei",
                "watch_person": "Dario Amodei",
                "content_type": "product_news",
                "is_leader_watch": True,
                "leader_watch_protected": True,
                "leader_priority": 10,
                "source": "Google News (Reuters)",
                "source_tier": 2,
                "published": "2026-08-17",
            },
        ]
        self.assertEqual(_source_tier(items[0]), 3)
        selected, overflow = _split_protected(items, max_protected=1)
        self.assertEqual(selected[0]["source"], "Google News (Reuters)")
        self.assertEqual(overflow[0]["source"], "Google News (Bitcoin World)")

    def test_known_reputable_sources_have_expected_tier(self):
        self.assertEqual(_source_tier({"source": "Google News (Reuters)", "source_tier": 3}), 2)
        self.assertEqual(_source_tier({"source": "Google News (Forbes)", "source_tier": 3}), 2)
        self.assertEqual(_source_tier({"source": "Google News (CNBC)", "source_tier": 3}), 2)


if __name__ == "__main__":
    unittest.main()
