from datetime import date

from src.trend_intelligence import TrendSignal, build_clusters
from src.trend_registry import TrendRegistry


def _signal(signal_id: str, title: str, source: str, day: int) -> TrendSignal:
    return TrendSignal(
        signal_id=signal_id,
        title=title,
        summary="agentic software engineering",
        source_id=source,
        source_tier="T1",
        evidence_level="expert_testimony",
        domain="ai",
        observed_on=date(2026, 8, day),
        novelty=0.8,
        strategic_impact=0.8,
        evidence_strength=0.7,
        mission_relevance=0.8,
    )


def test_registry_reuses_identity_when_signal_reappears(tmp_path):
    registry = TrendRegistry()
    first = registry.reconcile(build_clusters([_signal("a", "agentic engineering", "s1", 1)]))[0]
    second = registry.reconcile(build_clusters([_signal("a", "agentic engineering", "s1", 2)]))[0]
    assert first.cluster_id == second.cluster_id
    assert registry.clusters[first.cluster_id].signal_ids == ["a"]


def test_registry_persists_and_loads(tmp_path):
    path = tmp_path / "trend_registry.json"
    registry = TrendRegistry()
    record = registry.reconcile(build_clusters([_signal("a", "agentic engineering", "s1", 1)]))[0]
    registry.save(path)
    restored = TrendRegistry.load(path)
    assert restored.to_dict() == registry.to_dict()
    assert record.cluster_id in restored.clusters


def test_merge_and_split_are_auditable():
    registry = TrendRegistry()
    first = registry.reconcile(build_clusters([_signal("a", "agentic engineering", "s1", 1)]))[0]
    second = registry.reconcile(build_clusters([_signal("b", "quantum computing", "s2", 2)]))[0]
    merged = registry.merge(first.cluster_id, second.cluster_id)
    assert second.cluster_id in merged.parent_cluster_ids
    children = registry.split(merged.cluster_id, [["a"], ["b"]])
    assert len(children) == 2
    assert all(merged.cluster_id in child.parent_cluster_ids for child in children)
