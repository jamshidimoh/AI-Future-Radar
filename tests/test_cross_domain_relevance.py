from src.editorial_core import filter_ai_relevance


def test_quantum_ai_discovery_query_preserves_cross_domain_signal_without_article_ai_phrase():
    items = [{
        "title": "Researchers report a new quantum error-correction milestone",
        "summary": "The team reports improved error correction for a quantum processor.",
        "category": "quantum",
        "source_tier": 1,
        "content_type": "research",
        "discovery_query": "quantum machine learning AI breakthrough",
        "curated_discovery": False,
    }]

    result = filter_ai_relevance(items, ai_keywords=[])

    assert len(result) == 1
    assert result[0]["topic_family"] == "quantum_ai"
    assert result[0]["relevance_reason"] == "quantum_ai_bridge"
    assert result[0]["_ai_link"] is True


def test_generic_quantum_item_without_ai_discovery_context_is_still_rejected():
    items = [{
        "title": "Researchers report a quantum error-correction milestone",
        "summary": "The team reports improved error correction for a quantum processor.",
        "category": "quantum",
        "source_tier": 1,
        "content_type": "research",
        "discovery_query": "quantum error correction milestone",
        "curated_discovery": False,
    }]

    result = filter_ai_relevance(items, ai_keywords=[])

    assert result == []
