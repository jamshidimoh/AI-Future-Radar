"""Adaptive thresholds for semantic duplicate detection."""


def semantic_threshold(item, local=False):
    """Return a conservative duplicate threshold based on editorial context.

    The publication pipeline must prefer suppressing a likely repeated story
    over publishing the same event again merely because another source used a
    different headline or URL. Material updates remain distinguishable through
    the story-identity layer.
    """
    content_type = str(item.get("content_type") or "news").lower()
    leader = bool(item.get("leader") or item.get("watch_person") or item.get("_named_leader_interview"))
    breaking = bool(item.get("breaking_signal") or item.get("urgent"))

    if breaking:
        return 0.72 if local else 0.74
    if leader:
        return 0.68 if local else 0.70
    if content_type in {"research", "paper", "study", "preprint"}:
        return 0.66 if local else 0.68
    return 0.66 if local else 0.68
