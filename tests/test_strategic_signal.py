import unittest

from src.strategic_signal import strategic_forecast_score
from src.editorial import _apply_strategic_signal


class StrategicSignalTests(unittest.TestCase):
    def test_eric_schmidt_long_horizon_warning_gets_strategic_signal(self):
        item = {
            "title": "Eric Schmidt says AI could solve 1000-step problems within five years",
            "summary": "Multi-agent systems, infinite context, long-horizon reasoning and AI infrastructure risk.",
            "content_type": "interview",
            "mission_score": 20,
        }
        score = strategic_forecast_score(item)
        self.assertGreaterEqual(score, 20)
        self.assertTrue(item["strategic_forecast_signal"])
        self.assertTrue(item["strategic_risk_signal"])
        self.assertTrue(item["influential_person_signal"])

    def test_strategic_signal_is_independent_of_watchlist_flag(self):
        item = {
            "title": "A technology strategist forecasts multi-agent systems within five years",
            "summary": "The shift creates a national security and infrastructure risk.",
            "content_type": "interview",
            "mission_score": 15,
        }
        strategic_forecast_score(item)
        self.assertTrue(item["strategic_forecast_signal"])
        self.assertTrue(item["strategic_risk_signal"])
        self.assertFalse(item.get("is_leader_watch", False))

    def test_strategic_signal_changes_ranked_score(self):
        item = {
            "title": "Eric Schmidt discusses AI future",
            "summary": "Five years, multi-agent reasoning, human control and strategic risk.",
            "content_type": "interview",
            "mission_score": 10,
        }
        _apply_strategic_signal(item)
        self.assertGreater(item["mission_score"], item["mission_score_base"])


if __name__ == "__main__":
    unittest.main()
