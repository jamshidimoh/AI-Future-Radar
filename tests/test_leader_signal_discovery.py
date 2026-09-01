from src.fetch_google_news import _expand_leader_signal_queries


def test_leader_signal_expansion_adds_one_companion_per_person():
    queries = [
        {"query": "Elon Musk AI xAI future interview", "watch_person": "Elon Musk", "category": "ai", "tier": 1, "content_type": "interview"},
        {"query": "Elon Musk xAI product launch", "watch_person": "Elon Musk", "category": "ai", "tier": 1, "content_type": "product_news"},
        {"query": "Sam Altman AI AGI interview", "watch_person": "Sam Altman", "category": "ai", "tier": 1, "content_type": "interview"},
    ]

    expanded = _expand_leader_signal_queries(queries)
    companions = [q for q in expanded if q.get("content_type") == "leader_signal"]

    assert len(expanded) == len(queries) + 2
    assert {q["watch_person"] for q in companions} == {"Elon Musk", "Sam Altman"}
    assert all(q.get("leader_discovery") is True for q in companions)
    assert all(q.get("curated_discovery") is True for q in companions)
    assert all("Europe" in q["query"] for q in companions)
    assert all("policy" in q["query"] for q in companions)
    assert all("tweet" in q["query"] for q in companions)


def test_base_queries_without_leaders_are_unchanged():
    queries = [
        {"query": "AI drug discovery breakthrough", "category": "genetics", "tier": 1, "content_type": "research"}
    ]

    expanded = _expand_leader_signal_queries(queries)

    assert expanded == queries
