import inspect
import json
import time
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

    def _rank_item(self, title, source, score):
        return {
            "title": title,
            "summary": "A verified development in artificial intelligence research.",
            "content_type": "news",
            "source": source,
            "editorial_score": score,
            "published": "2026-08-22",
        }

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

    def test_ranked_selection_enforces_source_cap(self):
        items = [
            self._rank_item(f"Reddit {i}", "Reddit", 100 - i)
            for i in range(5)
        ] + [
            self._rank_item(f"Research {i}", "Research Institute", 80 - i)
            for i in range(3)
        ] + [
            self._rank_item(f"University {i}", "University Lab", 70 - i)
            for i in range(3)
        ]

        with patch.object(ranking, "_load_records", return_value=[]), patch.object(ranking._pipeline, "load_source_history", return_value=[]):
            selected = ranking._global_ranked_selection(
                items,
                max_posts=4,
                max_per_source=2,
                max_per_type=4,
                policy={"rotation_days": 7},
            )

        self.assertEqual(len(selected), 4)
        counts = {}
        for item in selected:
            source = item["source"]
            counts[source] = counts.get(source, 0) + 1
        self.assertTrue(all(count <= 2 for count in counts.values()))

    def test_ranked_selection_prefers_fresh_sources_but_backfills_from_recent_sources(self):
        items = [
            self._rank_item("Reddit recent 1", "Reddit", 100),
            self._rank_item("Reddit recent 2", "Reddit", 99),
            self._rank_item("Research fresh 1", "Research Institute", 90),
            self._rank_item("Research fresh 2", "Research Institute", 89),
            self._rank_item("University fresh 1", "University Lab", 88),
            self._rank_item("University fresh 2", "University Lab", 87),
        ]
        recent_ts = time.time() - 3600
        history = [
            {"ts": recent_ts, "source": "Reddit", "content_type": "news"},
            {"ts": recent_ts + 1, "source": "Reddit", "content_type": "news"},
        ]

        with patch.object(ranking, "_load_records", return_value=[]), patch.object(ranking._pipeline, "load_source_history", return_value=history):
            selected = ranking._global_ranked_selection(
                items,
                max_posts=4,
                max_per_source=2,
                max_per_type=4,
                policy={"rotation_days": 7},
            )

        selected_sources = [item["source"] for item in selected]
        self.assertEqual(len(selected), 4)
        self.assertLess(selected_sources.index("Reddit"), len(selected_sources))
        self.assertEqual(selected_sources.count("Research Institute"), 2)
        self.assertEqual(selected_sources.count("University Lab"), 1)
        self.assertEqual(selected_sources.count("Reddit"), 1)
        self.assertLess(selected_sources.index("Research Institute"), selected_sources.index("Reddit"))

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
