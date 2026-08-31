import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from education_editor import normalize_editorial_text, normalize_education_text
from educational_content import MIN_SOURCE_YEAR, load_curriculum
from educational_telegram_style import format_educational_post

RLI = "\u2067"
PDI = "\u2069"
LRI = "\u2066"
DIVIDERS = {"━━━━━━━━━━━━━━━━━━━━", "──────────────"}


class EducationalContentTests(unittest.TestCase):
    def _assert_rtl_structure(self, text):
        lines = [line for line in text.splitlines() if line and line not in DIVIDERS]
        self.assertGreaterEqual(len(lines), 10)
        rtl_blocks = sum(1 for line in lines if line.startswith(RLI))
        self.assertGreaterEqual(rtl_blocks, 8)
        self.assertEqual(text.count(PDI), text.count(RLI) + text.count(LRI))
        self.assertGreaterEqual(text.count(LRI), 4)
        self.assertGreaterEqual(text.count(RLI), 8)
        self.assertNotIn("\u202b", text)
        self.assertNotIn("\u202c", text)

    def test_curriculum_has_unique_sequential_lessons_and_two_terms(self):
        lessons = load_curriculum()["education"]["lessons"]
        self.assertGreaterEqual(len(lessons), 24)
        self.assertEqual([int(x["id"]) for x in lessons], list(range(1, len(lessons) + 1)))
        for lesson in lessons:
            self.assertTrue(lesson["a"]["term"] and lesson["b"]["term"])
            self.assertNotEqual(lesson["a"]["term"].strip().lower(), lesson["b"]["term"].strip().lower())
            self.assertGreaterEqual(len(lesson.get("sources") or []), 1)

    def test_source_floor_is_2025(self):
        self.assertEqual(MIN_SOURCE_YEAR, 2025)

    def test_news_guard_keeps_special_names_and_terms_english(self):
        text = normalize_editorial_text("دمیس هاسابیس درباره یادگیری ماشین، پلی‌کریسیس و پلی‌تونی‌تی صحبت کرد.")
        for expected in ("Demis Hassabis", "Machine Learning", "Polycrisis", "Polytunity"):
            self.assertIn(expected, text)
        for bad in ("دمیس هاسابیس", "پلی‌کریسیس", "پلی‌تونی‌تی"):
            self.assertNotIn(bad, text)

    def test_education_is_persian_first(self):
        text = normalize_education_text("یادگیری ماشین و شبکه عصبی برای آموزش مناسب‌اند.")
        self.assertIn("یادگیری ماشین", text)
        self.assertIn("شبکه عصبی", text)
        self.assertNotIn("Machine Learning", text)
        text = normalize_education_text("مهندسی کانتکست و لوپ انجینیرینگ و کدنویسی وایب")
        for expected in ("Context Engineering", "Loop Engineering", "Vibe Coding"):
            self.assertIn(expected, text)

    def _current_sources(self):
        return [
            {
                "name": "NIST AI Risk Management Framework",
                "url": "https://www.nist.gov/itl/ai-risk-management-framework",
                "year": 2026,
                "current_verified": True,
                "current_status": "maintained_current",
                "organization": "nist",
                "authority_tier": 1,
                "authority_score": 95,
            },
            {
                "name": "Stanford AI Index 2026",
                "url": "https://hai.stanford.edu/ai-index/2026-ai-index-report",
                "year": 2026,
                "current_verified": True,
                "current_status": "dated_current",
                "organization": "stanford",
                "authority_tier": 1,
                "authority_score": 95,
            },
        ]

    def _foundation_item(self):
        return {
            "education_number": 1,
            "education_track": "foundation",
            "education_term_a": "Artificial Intelligence (AI)",
            "education_term_a_fa": "هوش مصنوعی",
            "education_term_b": "Machine Learning (ML)",
            "education_term_b_fa": "یادگیری ماشین",
            "term_a_definition": "هوش مصنوعی مجموعه‌ای از روش‌ها و سامانه‌های محاسباتی است که برای انجام وظایفی به‌کار می‌روند که معمولاً به توانایی‌های هوشمندانهٔ انسان مانند درک، پیش‌بینی و تصمیم‌گیری نیاز دارند.",
            "term_a_simple": "به زبان ساده، هوش مصنوعی یعنی ساخت سامانه‌ای که بتواند از داده‌ها الگو بگیرد و برای یک مسئله مشخص پاسخ یا تصمیم مناسب تولید کند.",
            "term_b_definition": "یادگیری ماشین روشی در هوش مصنوعی است که در آن مدل با استفاده از داده و تجربه محاسباتی، الگوها و رابطه‌های قابل استفاده برای پیش‌بینی یا تصمیم‌گیری را یاد می‌گیرد.",
            "term_b_simple": "به‌جای نوشتن همهٔ قواعد به‌صورت دستی، نمونه‌هایی از داده به مدل می‌دهیم تا الگوی موردنیاز مسئله را از آن‌ها یاد بگیرد.",
            "relationship": "یادگیری ماشین یکی از روش‌های مهم برای ساخت سامانه‌های هوش مصنوعی است؛ بنابراین هوش مصنوعی مفهوم گسترده‌تر و یادگیری ماشین یکی از زیرشاخه‌های اصلی آن است.",
            "example": "برای نمونه، سامانه تشخیص هرزنامه می‌تواند با مشاهده هزاران پیام برچسب‌خورده یاد بگیرد که کدام الگوها بیشتر با پیام‌های ناخواسته ارتباط دارند و سپس پیام‌های جدید را طبقه‌بندی کند.",
            "takeaway": "نکته کلیدی این است که هوش مصنوعی هدف و حوزه کلی را بیان می‌کند، درحالی‌که یادگیری ماشین یکی از سازوکارهای اصلی رسیدن به این هدف از طریق یادگیری الگوها از داده است.",
            "education_sources": self._current_sources(),
        }

    def test_rendering_foundation_is_clean_persian_first(self):
        text = format_educational_post(self._foundation_item())
        self.assertIn("درس 01", text)
        self.assertIn("🧠", text)
        self.assertIn("<blockquote>", text)
        self.assertIn("<b>🔗 رابطه دو مفهوم</b>", text)
        self.assertIn("<b>🧩 مثال واقعی</b>", text)
        self.assertIn("<b>📌 نکته کلیدی</b>", text)
        self.assertIn("هوش مصنوعی", text)
        self.assertIn("یادگیری ماشین", text)
        self.assertIn("Artificial Intelligence (AI)", text)
        self.assertIn("Machine Learning (ML)", text)
        self.assertNotIn("AI FUTURE TECH RADAR", text)
        self.assertNotIn("AI Future Tech Radar", text)
        self._assert_rtl_structure(text)

    def test_rendering_emerging_keeps_canonical_term_without_branding(self):
        item = {
            "education_number": 2,
            "education_track": "emerging",
            "education_term_a": "Model Context Protocol (MCP)",
            "education_term_a_fa": "پروتکل مدل کانتکست",
            "education_term_b": "Vibe Coding",
            "education_term_b_fa": "کدنویسی مبتنی بر تعامل زبانی با هوش مصنوعی",
            "term_a_definition": "پروتکل مدل کانتکست یک استاندارد باز برای هماهنگ‌کردن مدل‌های هوش مصنوعی با ابزارها، داده‌ها و زمینه‌های بیرونی از طریق یک رابط مشخص است.",
            "term_a_simple": "به زبان ساده، این پروتکل راهی استاندارد برای وصل‌کردن مدل هوش مصنوعی به ابزارها و اطلاعاتی است که بیرون از خود مدل قرار دارند.",
            "term_b_definition": "Vibe Coding سبکی از تولید نرم‌افزار است که در آن توسعه‌دهنده بخش قابل‌توجهی از کدنویسی را با توصیف زبانی هدف و اصلاح تدریجی خروجی یک مدل هوش مصنوعی انجام می‌دهد.",
            "term_b_simple": "در این روش، فرد بیشتر روی توضیح مسئله و بازبینی نتیجه تمرکز می‌کند و مدل هوش مصنوعی بخش بیشتری از کد اولیه را تولید و اصلاح می‌کند.",
            "relationship": "هر دو مفهوم به همکاری انسان و مدل‌های مولد مربوط‌اند، اما پروتکل مدل کانتکست بر اتصال استاندارد مدل به ابزار و داده تمرکز دارد، درحالی‌که Vibe Coding بر شیوه استفاده از مدل برای تولید نرم‌افزار تمرکز می‌کند.",
            "example": "برای نمونه، یک توسعه‌دهنده می‌تواند از یک مدل متصل به ابزارهای پروژه برای خواندن مستندات و فایل‌های کد استفاده کند و سپس با دستورهای زبانی تغییرات موردنیاز را به‌صورت مرحله‌ای درخواست کند.",
            "takeaway": "نکته کلیدی این است که یک مفهوم زیرساخت ارتباط مدل با محیط بیرونی را استاندارد می‌کند و مفهوم دیگر یک شیوه عملی برای استفاده از مدل در فرایند توسعه نرم‌افزار را توصیف می‌کند.",
            "education_sources": self._current_sources(),
        }
        text = format_educational_post(item)
        self.assertIn("Model Context Protocol (MCP)", text)
        self.assertIn("Vibe Coding", text)
        self.assertIn("<b>📚 منابع منتخب</b>", text)
        self.assertNotIn("AI Future Tech Radar", text)
        self._assert_rtl_structure(text)


if __name__ == "__main__":
    unittest.main()