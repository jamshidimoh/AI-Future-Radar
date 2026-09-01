"""Canonical Story Gate and canonical score boundary.

Representative selection uses publication-value score only. Technology signal is
computed independently and combined once after deduplication.
"""
from editorial_score_v2 import score_editorial_v2
from story_identity import deduplicate_stories
from technology_signal_v2 import calculate_technology_signal_score


def _prepare_canonical_scores(item):
    candidate = dict(item)
    legacy_editorial = candidate.get("editorial_score")
    legacy_signal = candidate.get("signal_score")
    v2_editorial, features = score_editorial_v2(candidate)
    candidate["editorial_score_legacy"] = legacy_editorial
    candidate["signal_score_legacy"] = legacy_signal
    candidate["editorial_score_v2"] = v2_editorial
    candidate["editorial_features_v2"] = features
    candidate["editorial_score_pre_signal"] = v2_editorial
    vector = candidate.get("signal_vector") or {}
    if vector:
        signal_v2 = calculate_technology_signal_score(vector)
    else:
        try:
            signal_v2 = float(legacy_signal or 0)
        except (TypeError, ValueError):
            signal_v2 = 0.0
    candidate["technology_signal_score"] = round(signal_v2, 2)
    # Compatibility alias: all downstream canonical ranking paths now consume
    # the separated technology signal, while the legacy value is auditable.
    candidate["signal_score"] = candidate["technology_signal_score"]
    return candidate


def story_representative_rank_key(item):
    """Rank only by policy/authority/editorial publication value.

    Signal score and signal-inflated editorial score are intentionally absent.
    """
    try:
        representative_score = float(item.get("editorial_score_pre_signal", item.get("editorial_score", 0)) or 0)
    except (TypeError, ValueError):
        representative_score = 0.0
    return (
        int(item.get("leader_priority", 0) or 0),
        int(item.get("leader_source_authority", 0) or 0),
        1 if item.get("protected_content") else 0,
        representative_score,
        str(item.get("published", "")),
    )


def _canonical_final_editorial_score(item):
    """Combine canonical editorial and technology scores exactly once."""
    try:
        editorial = float(item.get("editorial_score_pre_signal", 0) or 0)
    except (TypeError, ValueError):
        editorial = 0.0
    try:
        signal = float(item.get("technology_signal_score", item.get("signal_score", 0)) or 0)
    except (TypeError, ValueError):
        signal = 0.0
    return round(0.75 * editorial + 0.25 * signal, 2)


def gate_story_candidates(protected_items, leader_items, regular_items, seen_signatures, threshold=0.45):
    """Prepare canonical scores, rank representatives once, then deduplicate."""
    ordered = []
    for pool in (protected_items or [], leader_items or [], regular_items or []):
        prepared = (_prepare_canonical_scores(item) for item in pool)
        ordered.extend(sorted(prepared, key=story_representative_rank_key, reverse=True))

    survivors = deduplicate_stories(ordered, history=list(seen_signatures or []))
    for item in survivors:
        item["final_editorial_score"] = _canonical_final_editorial_score(item)
        item["story_representative_score"] = story_representative_rank_key(item)[3]
    return survivors
