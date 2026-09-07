import unittest

from src.future_significance import annotate_future_significance, score_future_significance
from src.editorial import select_editorial


class FutureSignificanceTests(unittest.TestCase):
    def test_research_breakthrough_outscores_generic_product_tip(self):
        breakthrough = {
            "title": "New architecture achieves state of the art reasoning and scientific discovery",
            "summary": "Research findings demonstrate a new capability with implications for autonomous agents.",
            "content_type": "research",
            "source": "MIT CSAIL",
            "source_tier": 1,
            "category": "ai",
            "editorial_score": 75,
            "research_signal": True,
        }
        generic = {
            "title": "How to use ChatGPT: 10 new productivity tips",
            "summary": "A collection of prompts and tips for using ChatGPT.",
            "content_type": "news",
            "source": "Example Media",
            "source_tier": 2,
            "category": "ai",
            "editorial_score": 95,
        }
        b, _ = score_future_significance(breakthrough)
        g, _ = score_future_significance(generic)
        self.assertGreater(b, g)

    def test_annotation_preserves_editorial_score(self):
        item = {"title": "New AI capability", "summary": "research breakthrough", "editorial_score": 80}
        annotate_future_significance(item)
        self.assertEqual(item["editorial_score"], 80)
        self.assertIn("future_significance_score", item)
        self.assertIn("radar_composite_score", item)

    def test_selection_can_prefer_future_significance_without_quality_gate_bypass(self):
        items = [
            {
                "title": "How to use ChatGPT: 10 productivity tips",
                "summary": "prompt collection and productivity tips",
                "content_type": "news",
                "source": "A",
                "source_tier": 1,
                "category": "ai",
                "editorial_score": 100,
            },
            {
                "title": "Research breakthrough reveals new autonomous agent capability",
                "summary": "peer-reviewed study reports a new capability and future implications",
                "content_type": "research",
                "source": "B",
                "source_tier": 1,
                "category": "ai",
                "research_signal": True,
                "editorial_score": 85,
            },
            {
                "title": "AI and robotics breakthrough changes scientific discovery workflow",
                "summary": "new capability connects robotics and AI deployment",
                "content_type": "research",
                "source": "C",
                "source_tier": 1,
                "category": "robotics",
                "research_signal": True,
                "editorial_score": 84,
            },
        ]
        selected = select_editorial(items, max_posts=2, max_per_source=1, max_per_type=2, policy={"leader_interview_slots": 0})
        titles = [x["title"] for x in selected]
        self.assertNotIn("How to use ChatGPT: 10 productivity tips", titles)
        self.assertEqual(len(selected), 2)
        self.assertTrue(all("future_significance_score" in x for x in selected))


if __name__ == "__main__":
    unittest.main()
