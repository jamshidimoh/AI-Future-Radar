import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from editorial_clean import filter_ai_relevance


def _item(title, summary="", **extra):
    item = {
        "title": title,
        "summary": summary,
        "evidence_text": summary,
        "category": "ai",
        "content_type": "research",
        "source": "Test",
        "source_tier": 1,
    }
    item.update(extra)
    return item


def test_direct_ai_evidence_stays_high_confidence():
    result = filter_ai_relevance([
        _item(
            "New transformer architecture improves LLM inference",
            "Researchers evaluate a transformer architecture for large language model inference and report benchmark results.",
        )
    ], ["AI"])
    assert len(result) == 1
    assert result[0]["ai_relevance_confidence"] >= 0.9


def test_curated_provenance_without_any_ai_evidence_is_not_an_unbounded_bypass():
    result = filter_ai_relevance([
        _item(
            "New approach to urban irrigation discussed by Stanford scientists",
            "Soil moisture control and irrigation scheduling for city gardens.",
            source_type="news_aggregator",
            preferred_source="Stanford HAI",
            curated_discovery=True,
        )
    ], ["AI"])
    assert result == []


def test_curated_science_discovery_with_ai_method_evidence_is_retained():
    result = filter_ai_relevance([
        _item(
            "Scientists use a new method for scientific discovery",
            "The study uses machine learning to accelerate scientific discovery and evaluates the method on benchmark tasks.",
            source_type="news_aggregator",
            preferred_source="Stanford HAI",
            curated_discovery=True,
        )
    ], ["AI"])
    assert len(result) == 1
    assert result[0]["ai_relevance_confidence"] >= 0.8


def test_ai_gate_preserves_false_negative_bridges_for_future_and_mind_domains():
    items = [
        _item(
            "Forecast for the future of intelligence",
            "Researchers discuss AGI, reasoning systems and future technology trajectories.",
            category="future",
        ),
        _item(
            "New study of machine consciousness",
            "The study examines AI consciousness and cognitive architectures.",
            category="mind",
        ),
    ]
    result = filter_ai_relevance(items, ["AI"])
    assert len(result) == 2


def test_explicit_low_signal_content_remains_rejected_even_when_ai_is_mentioned():
    result = filter_ai_relevance([
        _item(
            "AI product review and unboxing",
            "A sponsored unboxing and product review of an AI gadget.",
            content_type="community",
        )
    ], ["AI"])
    assert result == []
