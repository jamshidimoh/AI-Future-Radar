import json
from pathlib import Path

from src.editorial import filter_ai_relevance
from src.semantic_dedup import _similarity
from src.unified_editorial_selection import select_regular_portfolio

ROOT = Path(__file__).resolve().parent / "characterization"


def test_semantic_similarity_characterization():
    fixture = json.loads((ROOT / "semantic_similarity.json").read_text(encoding="utf-8"))
    titles = fixture["titles"]
    for pair in fixture["pairs"]:
        assert round(_similarity(titles[pair["left"]], titles[pair["right"]]), 6) == pair["score"]
    for pair in fixture["raw_pairs"]:
        assert round(_similarity(pair["left"], pair["right"]), 6) == pair["score"]
    items = fixture["dict_items"]
    for pair in fixture["dict_pairs"]:
        assert round(_similarity(items[pair["left"]], items[pair["right"]]), 6) == pair["score"]


def test_select_regular_portfolio_characterization():
    fixture = json.loads((ROOT / "select_regular_portfolio.json").read_text(encoding="utf-8"))
    for case in fixture["grid"]:
        selected = select_regular_portfolio(
            fixture["candidates"],
            max_posts=case["max_posts"],
            max_per_source=case["max_per_source"],
            max_per_type=case["max_per_type"],
            recent_source_counts={"openai": 2, "reuters": 1},
            contract=fixture["contract"],
            mission_aware=case["mission_aware"],
            strict_relevance=case["strict_relevance"],
        )
        actual = [
            [item.get("title", ""), item.get("mission_selection_reason", ""), round(float(item.get("portfolio_information_gain", 0.0)), 6)]
            for item in selected
        ]
        assert actual == case["expected"]


def test_filter_ai_relevance_characterization():
    fixture = json.loads((ROOT / "filter_ai_relevance.json").read_text(encoding="utf-8"))
    for keywords, label in ((["machine learning", "neural"], "supplied"), (None, "bridge_only")):
        result = filter_ai_relevance(fixture["items"], keywords)
        actual = [
            {
                "title": item.get("title", ""),
                "relevance_reason": item.get("relevance_reason", ""),
                "ai_relevance_quality": item.get("ai_relevance_quality", ""),
                "ai_relevance_confidence": round(float(item.get("ai_relevance_confidence", 0.0)), 4),
                "evidence_strength": round(float(item.get("evidence_strength", 0.0)), 4),
                "early_inclusion": bool(item.get("early_inclusion")),
                "_ai_link": bool(item.get("_ai_link")),
            }
            for item in result
        ]
        assert actual == fixture["outputs"][label]
