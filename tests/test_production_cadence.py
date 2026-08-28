import unittest
from datetime import datetime

from production_entrypoint import _education_is_due, _education_slot, TEHRAN


class ProductionCadenceTests(unittest.TestCase):
    def test_morning_education_window(self):
        now = datetime(2026, 8, 28, 5, 17, tzinfo=TEHRAN)
        due, slot = _education_is_due(now, "")
        self.assertTrue(due)
        self.assertEqual(slot, "2026-08-28:morning")

    def test_evening_education_window(self):
        now = datetime(2026, 8, 28, 20, 47, tzinfo=TEHRAN)
        due, slot = _education_is_due(now, "")
        self.assertTrue(due)
        self.assertEqual(slot, "2026-08-28:evening")

    def test_non_education_news_window(self):
        now = datetime(2026, 8, 28, 10, 47, tzinfo=TEHRAN)
        due, slot = _education_is_due(now, "")
        self.assertFalse(due)
        self.assertIsNone(slot)

    def test_same_slot_is_not_repeated(self):
        now = datetime(2026, 8, 28, 5, 17, tzinfo=TEHRAN)
        due, slot = _education_is_due(now, "2026-08-28:morning")
        self.assertFalse(due)
        self.assertEqual(slot, "2026-08-28:morning")

    def test_failed_slot_can_retry_at_next_window(self):
        now = datetime(2026, 8, 28, 20, 47, tzinfo=TEHRAN)
        due, slot = _education_is_due(now, "2026-08-28:morning")
        self.assertTrue(due)
        self.assertEqual(slot, "2026-08-28:evening")

    def test_slot_boundaries(self):
        before = datetime(2026, 8, 28, 4, 59, tzinfo=TEHRAN)
        after = datetime(2026, 8, 28, 6, 31, tzinfo=TEHRAN)
        self.assertIsNone(_education_slot(before))
        self.assertIsNone(_education_slot(after))


if __name__ == "__main__":
    unittest.main()
