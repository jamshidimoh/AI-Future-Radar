import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from publication_contract import candidate_identity, delivery_result, unique_candidates


class PublicationContractTests(unittest.TestCase):
    def test_same_canonical_url_is_one_candidate(self):
        items = [
            {"title": "Story A", "link": "https://example.com/a?utm_source=x"},
            {"title": "Story A duplicate", "link": "https://example.com/a?utm_medium=y"},
        ]
        result = unique_candidates(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(candidate_identity(result[0]), "url:https://example.com/a")

    def test_same_title_without_url_is_one_candidate(self):
        items = [{"title": "Breaking: New AI model"}, {"title": "New AI model"}]
        result = unique_candidates(items)
        self.assertEqual(len(result), 1)

    def test_success_result_is_explicit(self):
        result = delivery_result({"ok": True, "chat_id": -100, "message_id": 42})
        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "published")

    def test_duplicate_reason_survives_legacy_false_result(self):
        with patch.dict(os.environ, {"AI_RADAR_PUBLICATION_GUARD_REASON": "semantic_story_already_published score=0.897"}, clear=False):
            result = delivery_result(False)
        self.assertFalse(result["ok"])
        self.assertTrue(result["reason"].startswith("semantic_story_already_published"))

    def test_transport_failure_has_explicit_default_reason(self):
        with patch.dict(os.environ, {}, clear=True):
            result = delivery_result(False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "telegram_delivery_failed")


if __name__ == "__main__":
    unittest.main()
