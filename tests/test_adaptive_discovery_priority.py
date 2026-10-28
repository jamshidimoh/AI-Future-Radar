from src.fetch_google_news import (
    _MAX_LEADER_SIGNAL_QUERIES,
    _expand_leader_signal_queries,
    _is_strong_curated_query,
    _query_content_type_priority,
)


def test_explicitly_curated_non_site_query_keeps_its_curated_status():
    query = {
        "query": '"Google DeepMind" interactive world simulator launch',
        "content_type": "product_news",
        "curated_discovery": True,
    }
    assert _is_strong_curated_query(query) is True


def test_product_and_strategic_queries_survive_bounded_leader_discovery_budget():
    people = [
        {
            "query": f'"Watched Leader {index}" interview AI future',
            "watch_person": f"Watched Leader {index}",
            "category": "ai",
            "tier": 1,
            "content_type": "interview",
        }
        for index in range(51)
    ]
    generic = [
        {
            "query": f"generic AI research topic {index}",
            "category": "ai",
            "tier": 1,
            "content_type": "research",
        }
        for index in range(100)
    ]
    product = {
        "query": '"Google DeepMind" Genie interactive world simulator launch',
        "category": "ai",
        "tier": 1,
        "content_type": "product_news",
        "curated_discovery": True,
    }
    strategy = {
        "query": '"Elon Musk" AI electricity power demand compute infrastructure statement',
        "category": "ai",
        "tier": 1,
        "content_type": "leader_signal",
        "curated_discovery": True,
    }
    expanded = _expand_leader_signal_queries(people + generic + [product, strategy])
    queries = {row["query"] for row in expanded}
    assert len(expanded) == _MAX_LEADER_SIGNAL_QUERIES
    assert product["query"] in queries
    assert strategy["query"] in queries


def test_product_and_strategic_queries_outrank_generic_research_queries():
    assert _query_content_type_priority({"content_type": "product_news"}) > _query_content_type_priority({"content_type": "research"})
    assert _query_content_type_priority({"content_type": "leader_signal"}) > _query_content_type_priority({"content_type": "research"})
