import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from educational_telegram_style import MAX_MESSAGE, format_educational_post


class EducationTelegramBudgetRegressionTests(unittest.TestCase):
    def test_long_education_payload_stays_within_canonical_single_message_budget(self):
        sources = [
            {"name": "NIST", "url": "https://www.nist.gov/", "year": 2026,
             "current_verified": True, "current_status": "maintained_current",
             "organization": "nist", "authority_tier": 1, "authority_score": 95},
            {"name": "Stanford HAI", "url": "https://hai.stanford.edu/", "year": 2026,
             "current_verified": True, "current_status": "dated_current",
             "organization": "stanford", "authority_tier": 1, "authority_score": 95},
        ]
        item = {
            "education_number": 41,
            "education_term_a": "Agent Architecture",
            "education_term_a_fa": "معماری عامل",
            "education_term_b": "Planning and State",
            "education_term_b_fa": "برنامه‌ریزی و وضعیت",
            "term_a_definition": "تعریف علمی معماری عامل و اجزای آن. " * 60,
            "term_a_simple": "توضیح ساده درباره معماری عامل. " * 30,
            "term_b_definition": "تعریف علمی برنامه‌ریزی و وضعیت در عامل. " * 60,
            "term_b_simple": "توضیح ساده درباره برنامه‌ریزی و وضعیت. " * 30,
            "relationship": "رابطه معماری، برنامه‌ریزی و وضعیت در یک عامل پژوهشی. " * 40,
            "example": "مثال واقعی از عامل پژوهشی و چرخه تصمیم‌گیری آن. " * 40,
            "takeaway": "نکته کلیدی درباره تفکیک معماری و برنامه‌ریزی. " * 25,
            "education_sources": sources,
        }
        text = format_educational_post(item)
        self.assertLessEqual(len(text), MAX_MESSAGE)
        self.assertLessEqual(len(text), 3900)


if __name__ == "__main__":
    unittest.main()
