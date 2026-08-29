import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from src.editorial import classify_editorial_item, filter_ai_relevance, enrich_items, select_editorial
from src.semantic_dedup import deduplicate_semantically
from src.send_telegram import _youtube_thumbnail
from summarize import _extract_json, _normalize
from llm_router_light import _select_hf_model
import main as pipeline


class QualityContractTests(unittest.TestCase):
    def test_cross_domain_gate(self):
        items = [
            {"title": "Qubit breakthrough", "summary": "new qubit hardware", "category": "quantum", "source": "A", "content_type": "research"},
            {"title": "Quantum machine learning", "summary": "quantum machine learning improves AI", "category": "quantum", "source": "B", "content_type": "research"},
            {"title": "AI breakthrough", "summary": "new AI agent", "category": "ai", "source": "C", "content_type": "research"},
        ]
        kept = filter_ai_relevance(items, ["AI", "machine learning", "agent"])
        self.assertEqual(len(kept), 2)
        self.assertTrue(all(x["_ai_link"] for x in kept))

    def test_named_leader_interview_is_protected(self):
        item = {"title": "Sam Altman on the next phase of AI", "summary": "Sam Altman discusses agents and the future of AI", "category": "ai", "source": "Leader", "content_type": "interview", "source_tier": 1, "official": True, "published": "2026-08-12 10:00", "watch_person": "Sam Altman", "is_leader_watch": True}
        enriched = enrich_items(filter_ai_relevance([item], ["AI", "agent", "AGI"]), {"Sam Altman": 10}, [], {})
        selected = select_editorial(enriched, 4, 2, 2)
        self.assertEqual(selected[0].get("leader"), "Sam Altman")
        self.assertEqual(selected[0].get("editorial_class"), "leader_interview")
        self.assertEqual(selected[0].get("editorial_slot"), "leader_interview")

    def test_leader_watch_channel_without_named_guest_is_not_protected_person_slot(self):
        item = {"title": "The future of AI agents", "summary": "a high-level AI interview", "category": "ai", "source": "Future of Life Institute", "source_type": "ai_safety", "content_type": "interview", "source_tier": 1, "official": True, "is_leader_watch": True}
        enriched = enrich_items(filter_ai_relevance([item], ["AI", "agent"]), {}, [], {})
        self.assertTrue(enriched[0].get("leader_signal"))
        selected = select_editorial(enriched, 1, 2, 2)
        self.assertEqual(selected[0].get("editorial_slot"), "fallback")

    def test_protected_leaders_escape_four_story_cap(self):
        leaders = [
            {"title": "Sam Altman interview", "summary": "Sam Altman discusses AI", "category": "ai", "source": "Leader A", "content_type": "interview", "source_tier": 1, "watch_person": "Sam Altman", "is_leader_watch": True},
            {"title": "Dario Amodei interview", "summary": "Dario Amodei discusses AI safety", "category": "ai", "source": "Leader B", "content_type": "interview", "source_tier": 1, "watch_person": "Dario Amodei", "is_leader_watch": True},
        ]
        regular = [
            {"title": f"Research {i}", "summary": "AI research benchmark", "category": "ai", "source": f"R{i}", "content_type": "research", "source_tier": 1}
            for i in range(8)
        ]
        items = filter_ai_relevance(leaders + regular, ["AI", "agent", "AGI"])
        enriched = enrich_items(items, {"Sam Altman": 10, "Dario Amodei": 10}, [], {})
        selected = select_editorial(enriched, 4, 2, 2, {"protected_slots": 4})
        leader_names = {x.get("leader") for x in selected if x.get("editorial_slot") == "leader_interview"}
        self.assertEqual(leader_names, {"Sam Altman", "Dario Amodei"})
        self.assertGreaterEqual(len(selected), 4)

    def test_interview_with_news_words_stays_leader_interview(self):
        item = {"title": "Demis Hassabis announces what comes next", "summary": "Conversation about new AI systems and research", "category": "ai", "content_type": "interview", "watch_person": "Demis Hassabis", "is_leader_watch": True}
        result = classify_editorial_item(item, {"Demis Hassabis": 10})
        self.assertEqual(result["editorial_class"], "leader_interview")

    def test_generic_interview_requires_ai_evidence(self):
        items = [
            {"title": "Intel CEO business story", "summary": "business story", "category": "ai", "source_type": "global_forum", "content_type": "interview"},
            {"title": "How AI agents reshape software", "summary": "AI agents and automation", "category": "ai", "source_type": "global_forum", "content_type": "interview"},
        ]
        kept = filter_ai_relevance(items, ["AI", "agent", "AGI"])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["relevance_reason"], "ai_evidence")

    def test_source_and_type_limits_remain_for_regular_pool(self):
        items = [
            {"title": f"News {i}", "summary": "AI launch", "category": "ai", "source": "Same", "content_type": "news", "source_tier": 1}
            for i in range(6)
        ]
        enriched = enrich_items(filter_ai_relevance(items, ["AI"]), {}, [], {})
        selected = select_editorial(enriched, 4, 1, 2)
        self.assertLessEqual(len(selected), 4)
        self.assertLessEqual(sum(x.get("source") == "Same" for x in selected), 1)

    def test_research_and_news_are_diversified(self):
        items = [
            {"title": "Research breakthrough", "summary": "AI benchmark research paper", "category": "ai", "source": "Research", "content_type": "research", "source_tier": 1},
            {"title": "Major model launch", "summary": "company announces new AI model", "category": "ai", "source": "News", "content_type": "news", "source_tier": 1},
        ]
        enriched = enrich_items(filter_ai_relevance(items, ["AI"]), {}, [], {})
        selected = select_editorial(enriched, 4, 2, 2)
        classes = {x.get("editorial_class") for x in selected}
        self.assertIn("research_breakthrough", classes)
        self.assertIn("major_industry_news", classes)

    def test_story_dedup_keeps_best_story(self):
        items = [
            {"title": "Sam Altman discusses AGI progress", "editorial_score": 30},
            {"title": "AGI progress discussed by Sam Altman", "editorial_score": 20},
        ]
        result = deduplicate_semantically(items, [], threshold=0.45)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["editorial_score"], 30)

    def test_quote_must_exist_in_source_text(self):
        item = {"category": "ai", "summary": "Sam said: AI agents will change software development."}
        valid = _normalize({"title": "x", "summary": "y", "why_it_matters": "z", "speakers": "Sam", "key_quote": "AI agents will change software development."}, item)
        invalid = _normalize({"title": "x", "summary": "y", "why_it_matters": "z", "speakers": "Sam", "key_quote": "This is an invented quotation."}, item)
        self.assertEqual(valid["key_quote"], "AI agents will change software development.")
        self.assertEqual(invalid["key_quote"], "")

    def test_hf_free_first_rejects_paid_explicit_model(self):
        models = [
            {"id": "paid-model", "free": False, "structured": True, "providers": 4, "throughput": 100, "latency": 10, "context": 10000, "input": 1.0, "output": 1.0},
            {"id": "free-model", "free": True, "structured": True, "providers": 2, "throughput": 80, "latency": 20, "context": 8000, "input": 0.0, "output": 0.0},
        ]
        with patch.dict(os.environ, {"HF_POLICY": "free-first", "HF_MODEL": "paid-model"}, clear=False), patch("llm_router_light._discover_hf_models", return_value=models):
            self.assertEqual(_select_hf_model(), "free-model")

    def test_llm_json_array_is_normalized_to_first_object(self):
        payload = '[{"title":"T","summary":"S","why_it_matters":"W","speakers":"","key_quote":"","category":"ai"}]'
        self.assertEqual(_extract_json(payload)["title"], "T")

    def test_youtube_thumbnail_resolution(self):
        expected = "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        self.assertEqual(_youtube_thumbnail("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), expected)
        self.assertEqual(_youtube_thumbnail("https://youtu.be/dQw4w9WgXcQ"), expected)
        self.assertIsNone(_youtube_thumbnail("https://example.com/article"))

    def test_main_helper_accepts_positional_compatibility_key(self):
        merged = pipeline._merge_unique_dicts([{"name": "A"}], [{"name": "B"}], key="name")
        self.assertEqual([x["name"] for x in merged], ["A", "B"])


if __name__ == "__main__":
    unittest.main()