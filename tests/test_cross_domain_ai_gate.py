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

def test_ai_query_does_not_rescue_unrelated_critical_materials_story():
    item = {
        "title": "Korea Zinc prioritizes critical mineral processing over mining",
        "summary": "The company plans to expand industrial materials processing for broad energy markets.",
        "category": "ai",
        "source_tier": 1,
        "discovery_query": "AI infrastructure, machine learning hardware and future technologies",
    }
    assert filter_ai_relevance([item], ai_keywords=[]) == []


def test_ai_query_does_not_rescue_unrelated_history_from_watched_person_feed():
    item = {
        "title": "Why Russian Tsars lost control of the empire",
        "summary": "A historical account of monarchy, imperial politics, and military conflict.",
        "category": "ai",
        "source_tier": 1,
        "discovery_query": "Dwarkesh Patel AI podcast and frontier AI interviews",
        "content_type": "podcast",
        "watch_person": "Dwarkesh Patel",
    }
    assert filter_ai_relevance([item], ai_keywords=[]) == []


def test_query_rescue_preserves_article_domain_family():
    item = {
        "title": "Quantum processor reaches a new error-correction milestone",
        "summary": "Researchers report better error correction on a quantum processor.",
        "category": "ai",
        "source_tier": 1,
        "discovery_query": "AI and quantum computing developments",
    }
    result = filter_ai_relevance([item], ai_keywords=[])
    assert len(result) == 1
    assert result[0]["topic_family"] == "quantum_ai"
    assert "article_domain_evidence" in result[0]["relevance_evidence"]

