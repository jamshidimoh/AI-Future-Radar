from src.trend_engine_v1 import (
    build_trend_clusters,
    enrich_with_trend_clusters,
    jaccard_similarity,
    validate_config,
)


BASE_CONFIG = {
    "similarity_threshold": 0.45,
    "minimum_cluster_size": 2,
    "high_confidence_threshold": 0.70,
    "score_weights": {
        "mean_signal": 0.45,
        "coherence": 0.25,
        "source_independence": 0.20,
        "mean_novelty": 0.10,
    },
}


def test_jaccard_similarity_is_deterministic_and_bounded():
    left = {"ai", "agents", "reasoning"}
    right = {"ai", "agents", "robotics"}
    assert jaccard_similarity(left, right) == 0.5
    assert 0.0 <= jaccard_similarity(left, right) <= 1.0
    assert jaccard_similarity(set(), set()) == 0.0


def test_repeated_execution_produces_identical_clusters():
    items = [
        {"id": "s1", "title": "AI agents improve research workflows", "signal_score": 70, "source": "source-a"},
        {"id": "s2", "title": "AI agents improve scientific research workflows", "signal_score": 72, "source": "source-b"},
        {"id": "s3", "title": "Quantum hardware maintenance update", "signal_score": 60, "source": "source-c"},
    ]
    first = build_trend_clusters(items, BASE_CONFIG)
    second = build_trend_clusters(items, BASE_CONFIG)
    assert first == second
    assert len(first) == 1
    assert first[0]["member_ids"] == ["s1", "s2"]


def test_complete_link_prevents_transitive_chain_from_becoming_one_cluster():
    items = [
        {"id": "a", "title": "alpha beta gamma delta", "signal_score": 40, "source": "a"},
        {"id": "b", "title": "alpha beta gamma epsilon", "signal_score": 45, "source": "b"},
        {"id": "c", "title": "alpha beta epsilon zeta", "signal_score": 50, "source": "c"},
    ]
    clusters = build_trend_clusters(items, BASE_CONFIG)
    assert all(cluster["cluster_size"] == 2 for cluster in clusters)
    assert sum(cluster["cluster_size"] for cluster in clusters) == 2


def test_weak_signal_cluster_is_retained_without_a_quality_floor():
    items = [
        {"id": "weak-a", "title": "novel AI inference architecture", "signal_score": 12, "source": "source-a"},
        {"id": "weak-b", "title": "novel AI inference architecture update", "signal_score": 14, "source": "source-b"},
    ]
    clusters = build_trend_clusters(items, BASE_CONFIG)
    assert len(clusters) == 1
    assert clusters[0]["mean_signal_score"] == 13.0
    assert clusters[0]["trend_class"] in {"candidate", "high"}


def test_source_independence_changes_trend_score_but_source_tier_does_not_define_it():
    common = {"title": "AI agents automate software research workflows", "signal_score": 80}
    same_source = build_trend_clusters(
        [dict(common, id="a", source="same"), dict(common, id="b", source="same")], BASE_CONFIG
    )[0]
    independent = build_trend_clusters(
        [dict(common, id="a", source="one"), dict(common, id="b", source="two")], BASE_CONFIG
    )[0]
    assert same_source["source_independence"] == 0.5
    assert independent["source_independence"] == 1.0
    assert independent["trend_score"] > same_source["trend_score"]
    tier_variant = build_trend_clusters(
        [dict(common, id="a", source="one", source_tier=1), dict(common, id="b", source="two", source_tier=3)], BASE_CONFIG
    )[0]
    assert tier_variant["trend_score"] == independent["trend_score"]


def test_enrichment_marks_unclustered_items_without_touching_publication_fields():
    items = [
        {"id": "a", "title": "AI agents improve research workflows", "signal_score": 70, "source": "a"},
        {"id": "b", "title": "Completely unrelated topic", "signal_score": 30, "source": "b"},
    ]
    enriched = enrich_with_trend_clusters(items, BASE_CONFIG)
    assert enriched[0]["trend_cluster_id"] is None
    assert enriched[1]["trend_cluster_id"] is None
    assert enriched[0]["signal_score"] == 70


def test_invalid_g1_configuration_fails_closed():
    invalid = dict(BASE_CONFIG, similarity_threshold=1.2)
    try:
        validate_config(invalid)
    except ValueError as exc:
        assert "similarity_threshold" in str(exc)
    else:
        raise AssertionError("invalid G1 configuration must fail closed")
