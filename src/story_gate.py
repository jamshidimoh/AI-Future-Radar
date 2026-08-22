"""Canonical Story Gate.

Selection priority is preserved here; duplicate identity is delegated to the
single Story Identity boundary. This prevents ranking/leader concerns from
silently redefining what a duplicate means.
"""
from story_identity import deduplicate_stories


def gate_story_candidates(protected_items, leader_items, regular_items, seen_signatures, threshold=0.45):
    """Order candidates once, then apply one conservative identity policy.

    ``threshold`` is retained for backwards compatibility with existing
    callers/configuration, but duplicate identity is no longer controlled by a
    broad semantic threshold. Related stories must remain eligible for ranking.
    """
    def rank(item):
        return (
            int(item.get("leader_priority", 0) or 0),
            int(item.get("leader_source_authority", 0) or 0),
            1 if item.get("protected_content") else 0,
            float(item.get("editorial_score", 0) or 0),
            float(item.get("signal_score", 0) or 0),
            str(item.get("published", "")),
        )

    ordered = []
    for pool in (protected_items or [], leader_items or [], regular_items or []):
        ordered.extend(sorted((dict(item) for item in pool), key=rank, reverse=True))

    return deduplicate_stories(ordered, history=list(seen_signatures or []))
