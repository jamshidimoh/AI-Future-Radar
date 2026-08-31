import unittest

from src.rtl_contract import PDI, RLI, force_rtl_blocks
from src.summarize import _fallback_title_from_persian_summary
from src.unified_editorial_selection import assert_portfolio_contract, select_regular_portfolio


class ProductionQualityRepairTests(unittest.TestCase):
    def test_research_portfolio_accepts_non_arxiv_research(self):
        items = [
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
                "research_signal": True,
            },
            {
                "title": "University AI research result",
                "summary": "artificial intelligence machine learning research result from a university lab",
                "content_type": "research",
                "source": "University Research Lab",
                "source_type": "research_institution",
                "canonical_url": "https://example.edu/research/ai",
                "source_tier": 1,
                "editorial_score": 87,
                "signal_score": 54,
                "editorial_confidence": 0.95,
                "category": "ai",
                "research_signal": True,
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
        selected = select_regular_portfolio(
            items,
            max_posts=3,
            max_per_source=2,
            max_per_type=2,
            recent_source_counts={},
            mission_aware=True,
            strict_relevance=True,
        )
        self.assertGreaterEqual(len(selected), 2)
        self.assertTrue(any(x.get("content_type") == "research" for x in selected))
        self.assertTrue(all("arxiv.org" not in str(x.get("canonical_url", "")).lower() for x in selected))
        self.assertTrue(all("arxiv" not in str(x.get("source", "")).lower() for x in selected))
        assert_portfolio_contract(selected)

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
