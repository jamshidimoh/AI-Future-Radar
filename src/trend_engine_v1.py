"""G1 deterministic signal-to-trend clustering.

This module is deliberately publication-decoupled. It consumes already-normalized
story/signal records and returns auditable current-window trend clusters. It does
not alter editorial eligibility, source authority, publication ranking, or
persistent lineage; those concerns belong to later gates.
"""
from __future__ import annotations

import hashlib
import re
from itertools import combinations
from typing import Any, Mapping, Sequence

DEFAULT_CONFIG: dict[str, Any] = {
    "similarity_threshold": 0.45,
    "minimum_cluster_size": 2,
    "high_confidence_threshold": 0.70,
    "score_weights": {
        "mean_signal": 0.45,
        "coherence": 0.25,
        "source_independence": 0.20,
        "mean_novelty": 0.10,
    },
    "stopwords": [],
}

_INTRINSIC_SIGNAL_WEIGHTS = {
    "novelty": 0.25,
    "future_impact": 0.25,
    "technical_significance": 0.20,
    "strategic_relevance": 0.15,
    "trend_alignment": 0.15,
}
_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


def _merged_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    result = dict(DEFAULT_CONFIG)
    source = dict(config or {})
    weights = dict(DEFAULT_CONFIG["score_weights"])
    weights.update(dict(source.get("score_weights") or {}))
    result.update(source)
    result["score_weights"] = weights
    result["stopwords"] = list(source.get("stopwords") or DEFAULT_CONFIG["stopwords"])
    return result


def validate_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate and return a normalized G1 configuration; fail closed on drift."""
    cfg = _merged_config(config)
    threshold = float(cfg["similarity_threshold"])
    minimum_size = int(cfg["minimum_cluster_size"])
    confidence = float(cfg["high_confidence_threshold"])
    weights = {key: float(value) for key, value in cfg["score_weights"].items()}

    if not 0.0 <= threshold <= 1.0:
        raise ValueError("similarity_threshold must be in [0, 1]")
    if minimum_size < 2:
        raise ValueError("minimum_cluster_size must be >= 2")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("high_confidence_threshold must be in [0, 1]")
    required = {"mean_signal", "coherence", "source_independence", "mean_novelty"}
    if set(weights) != required:
        raise ValueError("score_weights must contain exactly the four G1 dimensions")
    if any(value < 0.0 for value in weights.values()):
        raise ValueError("score_weights cannot be negative")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("score_weights must sum to 1.0")
    cfg["similarity_threshold"] = threshold
    cfg["minimum_cluster_size"] = minimum_size
    cfg["high_confidence_threshold"] = confidence
    cfg["score_weights"] = weights
    cfg["stopwords"] = {str(word).strip().lower() for word in cfg["stopwords"] if str(word).strip()}
    return cfg


def _signal_text(item: Mapping[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "summary", "description", "category")
    ).lower()


def token_set(item: Mapping[str, Any], stopwords: set[str] | None = None) -> set[str]:
    ignored = stopwords or set()
    return {token for token in _TOKEN_RE.findall(_signal_text(item)) if token not in ignored}


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _item_key(item: Mapping[str, Any], index: int) -> str:
    explicit = str(item.get("id") or item.get("story_id") or "").strip()
    if explicit:
        return explicit
    title = str(item.get("title") or "").strip().lower()
    if title:
        return title
    return f"item-{index}"


def _member_id(item: Mapping[str, Any], index: int) -> str:
    explicit = str(item.get("id") or item.get("story_id") or "").strip()
    if explicit:
        return explicit
    title = str(item.get("title") or "").strip()
    if title:
        return hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]
    return f"item-{index}"


def _similarity_matrix(items: Sequence[Mapping[str, Any]], stopwords: set[str]) -> list[list[float]]:
    tokens = [token_set(item, stopwords) for item in items]
    matrix = [[0.0 for _ in items] for _ in items]
    for left, right in combinations(range(len(items)), 2):
        value = jaccard_similarity(tokens[left], tokens[right])
        matrix[left][right] = value
        matrix[right][left] = value
    return matrix


def _complete_link_clusters(matrix: list[list[float]], threshold: float) -> list[list[int]]:
    """Greedily merge only when every cross-pair clears the threshold.

    Complete-link behavior prevents A-B-C transitive chains from becoming one
    cluster when A and C are not actually similar.
    """
    clusters: list[list[int]] = [[index] for index in range(len(matrix))]
    changed = True
    while changed:
        changed = False
        best: tuple[float, int, int] | None = None
        for left in range(len(clusters)):
            for right in range(left + 1, len(clusters)):
                cross = [matrix[a][b] for a in clusters[left] for b in clusters[right]]
                minimum = min(cross) if cross else 0.0
                if minimum < threshold:
                    continue
                candidate = (minimum, left, right)
                if best is None or candidate > best:
                    best = candidate
        if best is None:
            break
        _, left, right = best
        merged = sorted(clusters[left] + clusters[right])
        clusters = [cluster for index, cluster in enumerate(clusters) if index not in {left, right}]
        clusters.append(merged)
        clusters.sort(key=lambda cluster: (cluster[0], len(cluster), cluster))
        changed = True
    return clusters


def _score_0_100(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _signal_score(item: Mapping[str, Any]) -> float:
    """Return an intrinsic technology signal without Source Tier dependence."""
    for field in ("intrinsic_signal_score", "technology_signal_score"):
        if item.get(field) is not None:
            return _score_0_100(item.get(field))

    vector = item.get("signal_vector") or {}
    intrinsic = [
        float(vector[key]) * weight
        for key, weight in _INTRINSIC_SIGNAL_WEIGHTS.items()
        if isinstance(vector.get(key), (int, float))
    ]
    if intrinsic:
        total_weight = sum(
            weight for key, weight in _INTRINSIC_SIGNAL_WEIGHTS.items() if isinstance(vector.get(key), (int, float))
        )
        return max(0.0, min(100.0, sum(intrinsic) / total_weight * 10.0))

    # Explicit signal_score is accepted as a caller-supplied intrinsic score.
    # The G1 engine itself never derives that value from Source Tier.
    if item.get("signal_score") is not None:
        return _score_0_100(item.get("signal_score"))
    return 0.0


def _novelty_score(item: Mapping[str, Any]) -> float:
    vector = item.get("signal_vector") or {}
    if vector.get("novelty") is not None:
        return max(0.0, min(100.0, float(vector["novelty"]) * 10.0))
    return _score_0_100(item.get("novelty", 0.0))


def _source_key(item: Mapping[str, Any]) -> str:
    for field in ("source_id", "source", "source_name", "publisher"):
        value = str(item.get(field) or "").strip().lower()
        if value:
            return value
    return "unknown"


def _cluster_id(member_ids: Sequence[str]) -> str:
    payload = "|".join(sorted(str(value) for value in member_ids))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"trend-g1-{digest}"


def _coherence(indices: Sequence[int], matrix: list[list[float]]) -> float:
    if len(indices) < 2:
        return 0.0
    values = [matrix[left][right] for left, right in combinations(indices, 2)]
    return sum(values) / len(values)


def _cluster_confidence(size: int, source_independence: float, coherence: float, minimum_size: int) -> float:
    size_factor = min(1.0, max(0.0, (size - 1) / max(1, minimum_size)))
    return round(max(0.0, min(1.0, 0.30 * size_factor + 0.40 * source_independence + 0.30 * coherence)), 4)


def build_trend_clusters(
    items: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic current-window trend clusters from normalized signals."""
    cfg = validate_config(config)
    if not items:
        return []

    matrix = _similarity_matrix(items, cfg["stopwords"])
    components = _complete_link_clusters(matrix, cfg["similarity_threshold"])
    accepted = [cluster for cluster in components if len(cluster) >= cfg["minimum_cluster_size"]]
    weights = cfg["score_weights"]
    results: list[dict[str, Any]] = []

    for indices in accepted:
        member_items = [items[index] for index in indices]
        member_ids = sorted(_member_id(item, index) for item, index in zip(member_items, indices))
        sources = {_source_key(item) for item in member_items}
        if "unknown" in sources and len(sources) > 1:
            sources.remove("unknown")
        source_independence = len(sources) / len(member_items)
        coherence = _coherence(indices, matrix)
        mean_signal = sum(_signal_score(item) for item in member_items) / len(member_items)
        mean_novelty = sum(_novelty_score(item) for item in member_items) / len(member_items)
        trend_score = (
            mean_signal * weights["mean_signal"]
            + coherence * 100.0 * weights["coherence"]
            + source_independence * 100.0 * weights["source_independence"]
            + mean_novelty * weights["mean_novelty"]
        )
        confidence = _cluster_confidence(
            len(member_items), source_independence, coherence, cfg["minimum_cluster_size"]
        )
        representative_index = max(
            indices,
            key=lambda index: (_signal_score(items[index]), _item_key(items[index], index)),
        )
        results.append(
            {
                "cluster_id": _cluster_id(member_ids),
                "member_ids": member_ids,
                "cluster_size": len(member_items),
                "representative_id": _member_id(items[representative_index], representative_index),
                "mean_signal_score": round(mean_signal, 2),
                "mean_novelty_score": round(mean_novelty, 2),
                "coherence": round(coherence, 4),
                "source_independence": round(source_independence, 4),
                "trend_score": round(trend_score, 2),
                "trend_confidence": confidence,
                "trend_class": "high" if confidence >= cfg["high_confidence_threshold"] else "candidate",
            }
        )

    results.sort(key=lambda cluster: (-cluster["trend_score"], cluster["cluster_id"]))
    return results


def enrich_with_trend_clusters(
    items: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return copies annotated with current-window G1 trend metadata."""
    clusters = build_trend_clusters(items, config)
    by_member: dict[str, dict[str, Any]] = {}
    for cluster in clusters:
        for member_id in cluster["member_ids"]:
            by_member[member_id] = cluster

    enriched: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        result = dict(item)
        member_id = _member_id(item, index)
        cluster = by_member.get(member_id)
        if cluster is None:
            result.update(
                {
                    "trend_cluster_id": None,
                    "trend_score": 0.0,
                    "trend_confidence": 0.0,
                    "trend_class": "unclustered",
                }
            )
        else:
            result.update(
                {
                    "trend_cluster_id": cluster["cluster_id"],
                    "trend_score": cluster["trend_score"],
                    "trend_confidence": cluster["trend_confidence"],
                    "trend_class": cluster["trend_class"],
                }
            )
        enriched.append(result)
    return enriched
