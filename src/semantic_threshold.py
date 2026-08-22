"""Adaptive thresholds for semantic duplicate detection."""


def semantic_threshold(item, local=False):
    """Return duplicate similarity threshold based on editorial context."""
    content_type = str(item.get("content_type") or "news").lower()
    leader = bool(item.get("leader") or item.get("watch_person") or item.get("_named_leader_interview"))
    breaking = bool(item.get("breaking_signal") or item.get("urgent"))

    if breaking:
        return 0.70 if local else 0.72
    if leader:
        return 0.64 if local else 0.66
    if content_type in {"research", "paper", "study", "preprint"}:
        return 0.62 if local else 0.64
    return 0.60 if local else 0.62
