from __future__ import annotations

import importlib


def test_dynamic_candidates_keep_primary_first_and_add_topic_fallbacks():
    module = importlib.import_module("education_dynamic_sources")
    lesson = {
        "id": 113,
        "title": "Agentic Memory و Structured Memory",
        "domain": "AI agents",
        "a": {"term": "Agentic Memory", "seed": "memory for agents"},
        "b": {"term": "Structured Memory", "seed": "structured metadata"},
    }
    primary = {"name": "primary", "url": "https://example.com/primary"}
    candidates = module.dynamic_source_candidates(lesson, [primary], limit=8)
    assert candidates[0]["url"] == primary["url"]
    urls = {x["url"] for x in candidates}
    assert "https://learn.microsoft.com/en-us/ai/" in urls
    assert "https://www.ibm.com/docs/en/watsonx" in urls


def test_dynamic_candidates_are_deterministic():
    module = importlib.import_module("education_dynamic_sources")
    lesson = {
        "title": "AI agents evaluation",
        "domain": "AI",
        "a": {"term": "agent", "seed": "agent"},
        "b": {"term": "evaluation", "seed": "evaluation"},
    }
    first = [x["url"] for x in module.dynamic_source_candidates(lesson, [], limit=8)]
    second = [x["url"] for x in module.dynamic_source_candidates(lesson, [], limit=8)]
    assert first == second


def test_rank_verified_sources_prefers_relevance_then_authority():
    module = importlib.import_module("education_dynamic_sources")
    sources = [
        {"url": "https://low.example", "dynamic_relevance": 2, "authority_score": 99},
        {"url": "https://high.example", "dynamic_relevance": 8, "authority_score": 80},
    ]
    ranked = module.rank_verified_sources(sources)
    assert ranked[0]["url"] == "https://high.example"
