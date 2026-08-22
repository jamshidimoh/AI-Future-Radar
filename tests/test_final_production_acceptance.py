import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import period_ranked_pipeline as ranking
import production_entrypoint as production


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "publication_state.json"


class FinalProductionAcceptanceTests(unittest.TestCase):
    def _normal_items(self):
        return [
            {
                "title": f"AI research story {i}",
                "summary": "A verified development in artificial intelligence research.",
                "content_type": "news",
                "source": f"source-{i % 2}",
                "editorial_score": 90 - i,
                "published": f"2026-08-{10 + i:02d}",
            }
            for i in range(5)
        ]

    def test_ranked_selection_assigns_normal_rank_to_every_selected_normal_story(self):
        with patch.object(ranking, "_load_records", return_value=[]):
            selected = ranking._global_ranked_selection(
                self._normal_items(),
                max_posts=4,
                max_per_source=2,
                max_per_type=4,
                policy={"leader_interview_slots": 0},
            )

        self.assertGreaterEqual(len(selected), 1)
        self.assertTrue(all(item.get("period_rank") is not None for item in selected))
        normal_ranks = [item.get("normal_period_rank") for item in selected if not item.get("_rank_is_tier0")]
        self.assertEqual(normal_ranks, list(range(1, len(normal_ranks) + 1)))
        self.assertTrue(all(rank is not None for rank in normal_ranks))

    def test_period_ranked_pipeline_exports_ranked_selector(self):
        self.assertIs(ranking.select_editorial, ranking._global_ranked_selection)
        source = inspect.getsource(production.main)
        self.assertIn("original_select = pipeline.select_editorial", source)
        self.assertNotIn("from main import select_editorial", source)

    def test_production_state_contains_real_published_baseline(self):
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(int(state["run_number"]), 1)
        self.assertIsInstance(state.get("last_published_news_score"), (int, float))
        self.assertGreater(float(state["last_published_news_score"]), 0.0)
        self.assertIsInstance(state.get("last_published_normal_news_score"), (int, float))
        self.assertGreater(float(state["last_published_normal_news_score"]), 0.0)

    def test_single_publication_orchestrator_still_owns_selection_hook(self):
        source = inspect.getsource(production.main)
        self.assertEqual(source.count("original_select = pipeline.select_editorial"), 1)
        self.assertIn("unique_candidates(original_select(", source)


if __name__ == "__main__":
    unittest.main()
