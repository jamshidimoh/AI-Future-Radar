"""Quality gates before editorial ranking/publication."""
from __future__ import annotations


def quality_threshold(item):
    content_type = str(item.get("content_type") or "news").lower()
    if item.get("_named_leader_interview") or item.get("leader") or item.get("leader_signal") or item.get("is_leader_watch"):
        return 0.35
    if content_type in {"research", "paper", "study"}:
        return 0.45
    return 0.50


def quality_check(item):
    """Reject low-confidence candidates before final ranking."""
    score = float(item.get("editorial_score", 0) or 0)
    confidence = float(item.get("editorial_confidence", 0) or 0)
    minimum = quality_threshold(item)

    if confidence and confidence < minimum:
        return False, "low_confidence"
    if score < 0:
        return False, "negative_score"
    return True, "accepted"


def filter_quality_candidates(items):
    accepted = []
    rejected = []
    for item in items:
        ok, reason = quality_check(item)
        item["quality_gate_reason"] = reason
        if ok:
            accepted.append(item)
        else:
            rejected.append(item)
    print(f"[Quality Gate] accepted={len(accepted)} rejected={len(rejected)}", flush=True)
    return accepted
