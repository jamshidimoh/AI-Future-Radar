import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from educational_telegram_style import (
    MAX_DEFINITION,
    MAX_EXAMPLE,
    MAX_MESSAGE,
    MAX_RELATION,
    MAX_SIMPLE,
    MAX_TAKEAWAY,
    format_educational_post,
)
from summarize import _DRAFT_REPAIR_PROMPT, _PROMPT


class ExpandedSectionBudgetTests(unittest.TestCase):
    def test_news_prompt_requests_expanded_summary_and_why(self):
        self.assertIn("summary باید 3 تا 5 جمله کامل", _PROMPT)
        self.assertIn("why_it_matters باید 3 تا 4 جمله کامل و معمولاً 320 تا 500 نویسه", _PROMPT)
        self.assertIn("summary باید 3 تا 5 جمله کامل", _DRAFT_REPAIR_PROMPT)
        self.assertIn("why_it_matters باید 3 تا 4 جمله کامل و معمولاً 320 تا 500 نویسه", _DRAFT_REPAIR_PROMPT)

    def test_only_educational_concept_budgets_are_expanded(self):
        self.assertEqual(MAX_DEFINITION, 650)
        self.assertEqual(MAX_SIMPLE, 380)
        self.assertEqual(MAX_RELATION, 360)
        self.assertEqual(MAX_EXAMPLE, 380)
        self.assertEqual(MAX_TAKEAWAY, 240)

    def test_education_renderer_matches_canonical_telegram_safe_limit(self):
        self.assertEqual(MAX_MESSAGE, 3900)

    def test_education_still_fails_closed_above_single_message_budget(self):
        sources = [
            {"name": "NIST", "url": "https://www.nist.gov/", "year": 2026,
             "current_verified": True, "current_status": "maintained_current",
             "organization": "nist", "authority_tier": 1, "authority_score": 95},
            {"name": "Stanford", "url": "https://hai.stanford.edu/", "year": 2026,
             "current_verified": True, "current_status": "dated_current",
             "organization": "stanford", "authority_tier": 1, "authority_score": 95},
        ]
        item = {
            "education_number": 1,
            "education_term_a": "Artificial Intelligence (AI)",
            "education_term_a_fa": "هوش مصنوعی",
            "education_term_b": "Machine Learning (ML)",
            "education_term_b_fa": "یادگیری ماشین",
            "term_a_definition": "تعریف علمی کافی برای آزمون کیفیت و طول.",
            "term_a_simple": "توضیح ساده و قابل فهم برای مفهوم اول.",
            "term_b_definition": "تعریف علمی کافی برای مفهوم دوم و آزمون کیفیت.",
            "term_b_simple": "توضیح ساده و قابل فهم برای مفهوم دوم.",
            "relationship": "این دو مفهوم رابطه مشخص و قابل توضیحی دارند.",
            "example": "یک مثال واقعی و قابل فهم برای نمایش رابطه این دو مفهوم.",
            "takeaway": "نکته کلیدی درس بدون تغییر در قرارداد انتشار.",
            "education_sources": sources,
        }
        text = format_educational_post(item)
        self.assertLessEqual(len(text), MAX_MESSAGE)


if __name__ == "__main__":
    unittest.main()
