from src.education_dynamic_sources import build_candidate_pool

def test_memory_topic_has_fallbacks():
    lesson = {"title": "Agentic Memory and Structured Memory", "a": {"term": "Agentic Memory"}, "b": {"term": "Structured Memory"}}
    pool = build_candidate_pool(lesson, [{"name": "dead", "url": "https://example.invalid/dead"}])
    urls = {x["url"] for x in pool}
    assert "https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-memory-metadata.html" in urls
    assert "https://www.ibm.com/think/topics/ai-agent-memory" in urls
