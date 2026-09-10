from src.education_dynamic_sources import build_candidate_pool, independent_domains


def test_unavailable_configured_source_is_not_the_only_candidate():
    lesson = {"id": 113, "title": "Agentic Memory و Structured Memory", "a": {"term": "Agentic Memory", "seed": "agent memory"}, "b": {"term": "Structured Memory", "seed": "structured memory"}}
    configured = [{"name": "dead", "url": "https://example.invalid/dead"}]
    pool = build_candidate_pool(lesson, configured)
    urls = {x["url"] for x in pool}
    assert "https://example.invalid/dead" in urls
    assert "https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-memory-metadata.html" in urls
    assert "https://www.ibm.com/think/topics/ai-agent-memory" in urls


def test_topic_pool_contains_independent_authorities():
    lesson = {"title": "Agentic Memory", "a": {"term": "Agentic Memory"}, "b": {"term": "Structured Memory"}}
    pool = build_candidate_pool(lesson, [])
    assert independent_domains(pool) >= 3


def test_deterministic_order():
    lesson = {"title": "Agentic Memory", "a": {"term": "Agentic Memory"}, "b": {"term": "Structured Memory"}}
    first = [x["url"] for x in build_candidate_pool(lesson, [])]
    second = [x["url"] for x in build_candidate_pool(lesson, [])]
    assert first == second
