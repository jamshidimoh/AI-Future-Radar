from src.evidence_graph import Evidence, EvidenceGraph


def test_supporting_and_counter_evidence_are_separate():
    graph = EvidenceGraph()
    graph.extend([
        Evidence("e1", "source-a", "claim-1", "supporting", 0.8, "publisher-a"),
        Evidence("e2", "source-b", "claim-1", "counter", 0.4, "publisher-b"),
    ])
    assert len(graph.supporting("claim-1")) == 1
    assert len(graph.counter("claim-1")) == 1
    assert graph.net_evidence("claim-1") == (0.8 - 0.4) / 1.2


def test_reposts_do_not_count_as_independent_sources():
    graph = EvidenceGraph()
    graph.extend([
        Evidence("e1", "source-a", "claim-1", "supporting", 0.7, "origin-a"),
        Evidence("e2", "source-a-repost", "claim-1", "supporting", 0.7, "origin-a"),
        Evidence("e3", "source-b", "claim-1", "supporting", 0.6, "origin-b"),
    ])
    assert graph.independent_source_count("claim-1") == 2


def test_invalid_strength_is_rejected():
    try:
        Evidence("e1", "source-a", "claim-1", "supporting", 1.1)
    except ValueError:
        return
    raise AssertionError("invalid strength should be rejected")


def test_conflicting_duplicate_id_is_rejected():
    graph = EvidenceGraph()
    graph.add(Evidence("e1", "source-a", "claim-1", "supporting"))
    try:
        graph.add(Evidence("e1", "source-b", "claim-1", "supporting"))
    except ValueError:
        return
    raise AssertionError("conflicting duplicate evidence id should be rejected")
