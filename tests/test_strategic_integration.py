import unittest

from src.mission_selector import mission_score


class StrategicIntegrationTests(unittest.TestCase):
    def test_long_horizon_leader_interview_gets_strategic_bonus(self):
        strategic = {
            "title": "Eric Schmidt warns AI will reach 1000-step strategic reasoning within five years",
            "summary": "Eric Schmidt discusses multi-agent systems, infinite context, and loss of human control.",
            "why_it_matters": "The forecast combines long-horizon reasoning, multi-agent AI, and infrastructure risk.",
            "content_type": "interview",
            "source": "reputable interview",
            "source_format": "reputable_interview",
            "editorial_score": 4,
        }
        generic = {
            "title": "AI product update",
            "summary": "A routine model and app update.",
            "why_it_matters": "A routine product announcement.",
            "content_type": "product_news",
            "source": "reputable interview",
            "source_format": "news_report",
            "editorial_score": 4,
        }

        strategic_score = mission_score(strategic)
        generic_score = mission_score(generic)

        self.assertGreater(strategic.get("strategic_forecast_score", 0), 8)
        self.assertTrue(strategic.get("strategic_forecast_signal"))
        self.assertGreater(strategic_score, generic_score)


if __name__ == "__main__":
    unittest.main()
