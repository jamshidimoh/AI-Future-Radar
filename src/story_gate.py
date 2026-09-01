"""Canonical Story Gate.

Selection priority is preserved here; duplicate identity is delegated to the
single Story Identity boundary. Representative ranking must not consume the
signal-inflated intermediate editorial score or signal_score twice.
"""
from story_identity import deduplicate_stories


def story_representative_rank_key(item):
    """Return the ranking key used only to choose a story representative.

    The representative decision is intentionally independent of the signal
    score. ``editorial_score_pre_signal`` is preferred when available; legacy
    callers without it fall back to ``editorial_score``.
    """
    try:
        representative_score = float(
            item.get("editorial_score_pre_signal", item.get("editorial_score", 0)) or 0
        )
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
    """Compute the canonical final score used by portfolio selection."""
    try:
        pre_signal = float(
            item.get("editorial_score_pre_signal", item.get("editorial_score", 0)) or 0
        )
    except (TypeError, ValueError):
        pre_signal = 0.0
    try:
        signal = float(item.get("signal_score", 0) or 0)
    except (TypeError, ValueError):
        signal = 0.0
    if "editorial_score_pre_signal" not in item and "signal_score" not in item:
        return round(pre_signal, 2)
    return round(0.75 * pre_signal + 0.25 * signal, 2)


def gate_story_candidates(protected_items, leader_items, regular_items, seen_signatures, threshold=0.45):
    """Order candidates once, then apply one conservative identity policy.

    ``threshold`` is retained for backwards compatibility with existing
    callers/configuration, but duplicate identity is no longer controlled by a
    broad semantic threshold. Related stories must remain eligible for ranking.
    """
    ordered = []
    for pool in (protected_items or [], leader_items or [], regular_items or []):
        ordered.extend(
            sorted(
                (dict(item) for item in pool),
                key=story_representative_rank_key,
                reverse=True,
            )
        )

    survivors = deduplicate_stories(ordered, history=list(seen_signatures or []))
    for item in survivors:
        item["final_editorial_score"] = _canonical_final_editorial_score(item)
        item["story_representative_score"] = story_representative_rank_key(item)[3]
    return survivors
