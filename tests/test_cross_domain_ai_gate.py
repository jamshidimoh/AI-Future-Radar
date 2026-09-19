from src.editorial_core import filter_ai_relevance


def test_generic_quantum_without_ai_link_is_rejected():
    item = {
        "title": "Quantum processor reaches a new error-correction milestone",
        "summary": "Researchers report better error correction on a quantum processor.",
        "category": "quantum",
        "source_tier": 1,
        "discovery_query": "quantum error correction milestone",
    }
    assert filter_ai_relevance([item], ai_keywords=[]) == []


def test_quantum_is_rescued_by_ai_bearing_discovery_query_without_flattening():
    item = {
        "title": "Quantum processor reaches a new error-correction milestone",
        "summary": "Researchers report better error correction on a quantum processor.",
        "category": "quantum",
        "source_tier": 1,
        "discovery_query": "quantum machine learning AI breakthrough",
    }
    result = filter_ai_relevance([item], ai_keywords=[])
    assert len(result) == 1
    assert result[0]["topic_family"] == "quantum_ai"
    assert result[0]["relevance_reason"] == "quantum_ai_bridge"
    assert result[0]["_ai_link"] is True


def test_quantum_ai_article_text_stays_cross_domain():
    item = {
        "title": "Quantum machine learning model improves optimization",
        "summary": "A quantum machine learning approach improves an optimization task.",
        "category": "quantum",
        "source_tier": 1,
    }
    result = filter_ai_relevance([item], ai_keywords=[])
    assert result[0]["topic_family"] == "quantum_ai"
