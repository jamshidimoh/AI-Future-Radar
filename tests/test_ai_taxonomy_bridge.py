import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from editorial import filter_ai_relevance


def _item(title, summary=""):
    return {
        "title": title,
        "summary": summary,
        "evidence_text": summary,
        "category": "ai",
        "content_type": "research",
        "source": "Test",
        "source_tier": 1,
    }


def test_gpt_is_ai_relevant():
    result = filter_ai_relevance([_item("GPT-5 reasoning model benchmark")], ["AI"])
    assert len(result) == 1


def test_transformer_is_ai_relevant():
    result = filter_ai_relevance([_item("New transformer architecture for inference")], ["AI"])
    assert len(result) == 1


def test_neural_network_is_ai_relevant():
    result = filter_ai_relevance([_item("Neural network scaling study")], ["AI"])
    assert len(result) == 1


def test_unrelated_topic_stays_rejected():
    result = filter_ai_relevance([_item("Urban gardening trends", "Soil preparation and irrigation only.")], ["AI"])
    assert result == []
