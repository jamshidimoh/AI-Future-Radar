import unittest

from src.portfolio_selection import select_normal_portfolio
from src.rtl_contract import PDI, RLI, force_rtl_blocks
from src.summarize import _fallback_title_from_persian_summary


class ProductionQualityRepairTests(unittest.TestCase):
    def test_final_portfolio_limits_arxiv_to_one_when_alternatives_exist(self):
        items = [
            {
                "title": "AI benchmark paper one",
                "summary": "artificial intelligence machine learning research benchmark",
                "content_type": "research",
                "source": "arXiv cs.LG",
                "source_type": "scientific_repository",
                "canonical_url": "https://arxiv.org/abs/1",
                "source_tier": 2,
                "editorial_score": 92,
                "signal_score": 60,
                "editorial_confidence": 0.95,
                "category": "ai",
            },
            {
                "title": "Bioinformatics research result",
                "summary": "AI biology genomics research result from a university lab",
                "content_type": "research",
                "source": "Nature News",
                "source_type": "news",
                "canonical_url": "https://example.org/nature",
                "source_tier": 1,
                "editorial_score": 88,
                "signal_score": 55,
                "editorial_confidence": 0.95,
                "category": "genetics",
            },
            {
                "title": "AI benchmark paper two",
                "summary": "artificial intelligence machine learning research benchmark second study",
                "content_type": "research",
                "source": "arXiv q-bio.GN",
                "source_type": "scientific_repository",
                "canonical_url": "https://arxiv.org/abs/2",
                "source_tier": 2,
                "editorial_score": 91,
                "signal_score": 59,
                "editorial_confidence": 0.95,
                "category": "genetics",
            },
            {
                "title": "Frontier AI interview",
                "summary": "interview conversation about AGI and the future of AI",
                "content_type": "interview",
                "source": "Lex Fridman Podcast",
                "source_type": "podcast",
                "source_tier": 1,
                "editorial_score": 84,
                "signal_score": 50,
                "editorial_confidence": 0.95,
                "category": "ai",
                "interview_signal": True,
            },
        ]
        selected = select_normal_portfolio(items, max_posts=4, max_per_source=2, max_per_type=2, policy={})
        arxiv = [x for x in selected if "arxiv" in str(x.get("source", "")).lower()]
        self.assertEqual(len(arxiv), 1)
        self.assertGreaterEqual(len(selected), 3)

    def test_provider_independent_title_fallback_uses_validated_persian_summary(self):
        data = {
            "title": "Who Is Claude Actually Aligned To - Ryan Greenblatt",
            "summary": "این گفت‌وگو درباره هم‌ترازی مدل‌های هوش مصنوعی، محدودیت‌های روش‌های فعلی و مسیرهای آینده پژوهش در این حوزه است.",
            "why_it_matters": "این بحث برای ارزیابی مسیر هم‌ترازی مدل‌ها و فهم ریسک‌های آینده هوش مصنوعی اهمیت دارد.",
        }
        repaired = _fallback_title_from_persian_summary(data)
        self.assertIsNotNone(repaired)
        self.assertGreaterEqual(len(repaired["title"]), 10)
        self.assertRegex(repaired["title"], r"[\u0600-\u06ff]")

    def test_rtl_contract_wraps_every_nonempty_block(self):
        rendered = force_rtl_blocks("عنوان فارسی\n\nGoogle Gemini 3")
        blocks = rendered.splitlines()
        self.assertTrue(blocks[0].startswith(RLI) and blocks[0].endswith(PDI))
        self.assertEqual(blocks[1], "")
        self.assertTrue(blocks[2].startswith(RLI) and blocks[2].endswith(PDI))


if __name__ == "__main__":
    unittest.main()
