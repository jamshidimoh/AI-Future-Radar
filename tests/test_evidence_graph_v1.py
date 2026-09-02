import pytest

from src.evidence_graph_v1 import (
    build_evidence_graph,
    canonical_source_url,
    claim_id,
    graph_snapshot,
    source_id,
    trend_id,
    validate_graph,
)


def test_canonical_source_url_removes_tracking_and_normalizes_host():
    assert canonical_source_url("HTTPS://Example.COM/story/?utm_source=x&b=2#fragment") == "https://example.com/story?b=2"


def test_source_and_claim_ids_are_stable():
    source = {"url": "https://example.com/story", "title": "Story"}
    assert source_id(source) == source_id(dict(source))
    assert claim_id("OpenAI released a new model") == claim_id(" OpenAI released a new model ")


def test_graph_contains_explicit_support_and_contradiction_edges():
    graph = build_evidence_graph(
        [
            {
                "url": "https://a.example/news/1",
                "title": "Model launch",
                "source_type": "primary",
                "claims": [
                    "The model was released in June.",
                    {"text": "The model is open weight.", "relation": "supports", "confidence": 0.9},
                    {"text": "The model has no multimodal capability.", "relation": "contradicts", "confidence": 0.7},
                ],
            }
        ]
    )
    relations = {(edge["relation"], edge["confidence"]) for edge in graph["edges"]}
    assert ("supports", 1.0) in relations
    assert ("supports", 0.9) in relations
    assert ("contradicts", 0.7) in relations


def test_duplicate_source_urls_do_not_create_duplicate_source_nodes():
    graph = build_evidence_graph(
        [
            {"url": "https://example.com/story?utm_campaign=a", "title": "A", "claims": ["Same claim"]},
            {"url": "https://EXAMPLE.com/story?utm_medium=b", "title": "A", "claims": ["Same claim"]},
        ]
    )
    sources = [node for node in graph["nodes"] if node["type"] == "source"]
    claims = [node for node in graph["nodes"] if node["type"] == "claim"]
    assert len(sources) == 1
    assert len(claims) == 1


def test_trend_can_derive_from_existing_claims():
    base = build_evidence_graph(
        [{"url": "https://example.com/1", "title": "One", "claims": ["A stable claim"]}]
    )
    cid = next(node["id"] for node in base["nodes"] if node["type"] == "claim")
    graph = build_evidence_graph(
        [{"url": "https://example.com/1", "title": "One", "claims": ["A stable claim"]}],
        [{"cluster_id": "trend-g2-test", "claim_ids": [cid], "confidence": 0.8, "label": "Trend"}],
    )
    edge = next(edge for edge in graph["edges"] if edge["relation"] == "derived_from")
    assert edge["source"] == cid
    assert edge["target"] == "trend-g2-test"
    assert edge["confidence"] == 0.8


def test_graph_is_deterministic_under_input_order():
    sources_a = [
        {"url": "https://example.com/b", "title": "B", "claims": ["Claim B"]},
        {"url": "https://example.com/a", "title": "A", "claims": ["Claim A"]},
    ]
    sources_b = list(reversed(sources_a))
    assert build_evidence_graph(sources_a) == build_evidence_graph(sources_b)


def test_unknown_trend_claim_fails_closed():
    with pytest.raises(ValueError, match="unknown claim"):
        build_evidence_graph(
            [{"url": "https://example.com/1", "title": "One", "claims": ["Known"]}],
            [{"cluster_id": "trend-1", "claim_ids": ["claim-does-not-exist"]}],
        )


def test_invalid_relation_fails_closed():
    with pytest.raises(ValueError, match="unsupported relation"):
        build_evidence_graph(
            [{"url": "https://example.com/1", "title": "One", "claims": [{"text": "Claim", "relation": "guesses"}]}]
        )


def test_invalid_graph_schema_fails_closed():
    with pytest.raises(ValueError, match="schema_version"):
        validate_graph({"schema_version": 99, "nodes": [], "edges": []})


def test_graph_snapshot_is_canonical_and_validated():
    graph = build_evidence_graph(
        [{"url": "https://example.com/1", "title": "One", "claims": ["Claim"]}]
    )
    assert graph_snapshot(graph) == validate_graph(graph)


def test_empty_source_requires_title_or_url():
    with pytest.raises(ValueError, match="URL or title"):
        source_id({})


def test_empty_claim_fails_closed():
    with pytest.raises(ValueError, match="claim text"):
        claim_id("   ")


def test_trend_identity_is_stable_from_members():
    value = {"member_ids": ["b", "a"]}
    assert trend_id(value) == trend_id({"member_ids": ["a", "b"]})
