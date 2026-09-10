import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import educational_content as education


class EducationSelectionRegressionTests(unittest.TestCase):
    def _sequence(self):
        return [
            ("foundation", {"id": 1, "title": "One"}),
            ("foundation", {"id": 2, "title": "Two"}),
            ("foundation", {"id": 3, "title": "Three"}),
        ]

    def test_selects_first_uncompleted_in_curriculum_order(self):
        with patch.object(education, "_lesson_sequence", return_value=self._sequence()), \
             patch.object(education, "load_state", return_value={"completed": [1]}):
            lesson, lesson_id, total = education._next_lesson()
        self.assertEqual(lesson_id, 2)
        self.assertEqual(lesson["title"], "Two")
        self.assertEqual(total, 3)

    def test_exhausted_curriculum_fails_closed_instead_of_wrapping_to_lesson_one(self):
        with patch.object(education, "_lesson_sequence", return_value=self._sequence()), \
             patch.object(education, "load_state", return_value={"completed": [1, 2, 3]}):
            lesson, lesson_id, total = education._next_lesson()
        self.assertIsNone(lesson)
        self.assertEqual(lesson_id, 0)
        self.assertEqual(total, 3)

    def test_commit_advances_to_first_pending_lesson(self):
        state = {"completed": [1], "next_lesson": 1, "next_slot": 0}
        with patch.object(education, "_lesson_sequence", return_value=self._sequence()), \
             patch.object(education, "load_state", return_value=state), \
             patch.object(education, "save_state") as save_state:
            education.commit_education_lesson(1)
        saved = save_state.call_args.args[0]
        self.assertEqual(saved["next_lesson"], 2)
        self.assertEqual(saved["next_slot"], 1)
        self.assertEqual(saved["completed"], [1])

    def test_commit_sets_zero_pointer_when_curriculum_becomes_exhausted(self):
        state = {"completed": [1, 2], "next_lesson": 2, "next_slot": 1}
        with patch.object(education, "_lesson_sequence", return_value=self._sequence()), \
             patch.object(education, "load_state", return_value=state), \
             patch.object(education, "save_state") as save_state:
            education.commit_education_lesson(3)
        saved = save_state.call_args.args[0]
        self.assertEqual(saved["next_lesson"], 0)
        self.assertEqual(saved["next_slot"], 3)
        self.assertEqual(saved["completed"], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
