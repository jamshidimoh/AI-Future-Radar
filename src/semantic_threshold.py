"""Adaptive thresholds for semantic duplicate detection.

Semantic similarity is a fallback safety net, not the primary definition of
story identity. Same-person, same-company, same-product-family and same-topic
stories must remain distinct unless the event/story identity layer corroborates
a duplicate.
"""


def semantic_threshold(item, local=False):
    """Return a high-confidence fallback threshold for semantic similarity.

    The event/story identity layer is authoritative. These thresholds are kept
    high so raw lexical/semantic overlap cannot suppress independent stories.
    """
    content_type = str(item.get("content_type") or "news").lower()
    leader = bool(item.get("leader") or item.get("watch_person") or item.get("_named_leader_interview"))
    breaking = bool(item.get("breaking_signal") or item.get("urgent"))

    if breaking:
        return 0.84 if local else 0.86
    if leader:
        return 0.86 if local else 0.88
    if content_type in {"research", "paper", "study", "preprint"}:
        return 0.87 if local else 0.89
    return 0.88 if local else 0.90
