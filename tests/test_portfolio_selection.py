import unittest

from src.portfolio_selection import select_normal_portfolio


class MissionAwarePortfolioTests(unittest.TestCase):
    def test_low_confidence_candidate_is_rejected_before_selection(self):
        items = [
            {
                "title": "Gemini",
                "summary": "AI content",
                "content_type": "news",
                "source": "Example",
                "source_tier": 1,
                "editorial_score": 100,
                "editorial_confidence": 0.35,
            },
            {
                "title": "Frontier AI research result",
                "summary": "new model research breakthrough",
                "content_type": "research",
                "source": "Nature",
                "source_tier": 1,
                "editorial_score": 80,
                "editorial_confidence": 0.90,
                "research_signal": True,
                "category": "ai",
            },
        ]
        selected = select_normal_portfolio(items, max_posts=2, max_per_source=2, max_per_type=2, policy={})
        self.assertEqual([x["title"] for x in selected], ["Frontier AI research result"])

    def test_mission_family_diversity_can_surface_non_ai_signal(self):
        items = [
            {
                "title": "Major AI product launch",
                "summary": "new AI model released",
                "content_type": "news",
                "source": "Reuters",
                "source_tier": 2,
                "editorial_score": 88,
                "editorial_confidence": 0.90,
                "category": "ai",
            },
            {
                "title": "Quantum machine learning breakthrough",
                "summary": "quantum computing machine learning research breakthrough",
                "content_type": "research",
                "source": "arXiv quant-ph",
                "source_tier": 1,
                "editorial_score": 84,
                "editorial_confidence": 0.95,
                "category": "quantum",
                "research_signal": True,
            },
            {
                "title": "AI company funding round",
                "summary": "AI startup funding investment",
                "content_type": "news",
                "source": "TechCrunch",
                "source_tier": 2,
                "editorial_score": 82,
                "editorial_confidence": 0.90,
                "category": "ai",
            },
            {
                "title": "Another AI model release",
                "summary": "new model release",
                "content_type": "news",
                "source": "The Verge",
                "source_tier": 2,
                "editorial_score": 80,
                "editorial_confidence": 0.90,
                "category": "ai",
            },
        ]
        selected = select_normal_portfolio(items, max_posts=3, max_per_source=1, max_per_type=2, policy={})
        areas = {x.get("mission_area") for x in selected}
        self.assertIn("convergence", areas)
        self.assertIn("ai_core", areas)

    def test_interview_and_research_are_not_starved_by_same_type_fill(self):
        items = [
            {
                "title": "AI research result",
                "summary": "research findings new capability",
                "content_type": "research",
                "source": "MIT News",
                "source_tier": 1,
                "editorial_score": 86,
                "editorial_confidence": 0.95,
                "category": "ai",
                "research_signal": True,
            },
            {
                "title": "Frontier AI leader interview",
                "summary": "interview conversation about AGI and future of AI",
                "content_type": "interview",
                "source": "Lex Fridman Podcast",
                "source_tier": 1,
                "editorial_score": 84,
                "editorial_confidence": 0.95,
                "category": "ai",
                "interview_signal": True,
                "leader": "Sam Altman",
            },
            {
                "title": "AI market update",
                "summary": "AI industry news",
                "content_type": "news",
                "source": "Reuters",
                "source_tier": 2,
                "editorial_score": 83,
                "editorial_confidence": 0.95,
                "category": "ai",
            },
        ]
        selected = select_normal_portfolio(items, max_posts=3, max_per_source=1, max_per_type=2, policy={})
        types = [str(x.get("content_type")) for x in selected]
        self.assertIn("research", types)
        self.assertIn("interview", types)
        self.assertIn("news", types)


if __name__ == "__main__":
    unittest.main()
