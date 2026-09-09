"""Single Story-to-Publication orchestration boundary.

This module owns the decision boundary between editorial policy, transport,
and the publication ledger. Callers provide the concrete policy, delivery,
and ledger functions; lower layers must not make publication decisions.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from src.delivery_contract import DeliveryOutcome, DeliveryStatus, duplicate, policy_blocked, rejected, transport_failed


Policy = Callable[[Mapping[str, Any]], DeliveryOutcome]
Deliver = Callable[[Mapping[str, Any]], DeliveryOutcome]
Ledger = Callable[[Mapping[str, Any], DeliveryOutcome], None]

_CURRENT_RUN_PUBLICATIONS: list[dict[str, Any]] = []


def _final_story_guard(story: Mapping[str, Any]) -> tuple[bool, str]:
    """Apply the same publication-history guard at the actual send boundary.

    The guard is intentionally activated only for rendered production stories;
    lower-level unit tests and non-Telegram callers without rendered payloads
    retain their existing policy contract.
    """
    rendered = str(story.get("_rendered_text") or "").strip()
    if not rendered:
        return True, "not_rendered"
    try:
        from src.publication_guard import check_before_publish
        return check_before_publish(
            rendered,
            str(story.get("link") or story.get("url") or ""),
            records=_CURRENT_RUN_PUBLICATIONS,
        )
    except Exception as exc:
        print(f"[Final Publication Guard] unavailable: {exc}; publication BLOCKED", flush=True)
        return False, "publication_guard_unavailable"


def _remember_current_run_publication(story: Mapping[str, Any]) -> None:
    _CURRENT_RUN_PUBLICATIONS.append(
        {
            "title": str(story.get("title") or "").strip(),
            "summary": str(story.get("summary") or story.get("description") or "").strip(),
            "link": str(story.get("link") or story.get("url") or "").strip(),
            "leader": str(story.get("leader") or story.get("watch_person") or "").strip(),
        }
    )


def publish_story(
    story: Mapping[str, Any],
    *,
    policy: Policy,
    deliver: Deliver,
    ledger: Ledger,
) -> DeliveryOutcome:
    """Execute exactly one publication attempt for one Story.

    Policy rejection never reaches transport. A known final-story conflict
    never reaches transport. Transport failure never reaches the ledger. The
    ledger is called only after a confirmed Telegram ``message_id`` is present
    in a DELIVERED outcome.
    """
    decision = policy(story)
    if decision.status in {
        DeliveryStatus.REJECTED,
        DeliveryStatus.DUPLICATE,
        DeliveryStatus.POLICY_BLOCKED,
    }:
        return decision

    if decision.status is not DeliveryStatus.DELIVERED and decision.message_id is not None:
        return transport_failed("invalid_policy_outcome", retryable=False)

    allowed, reason = _final_story_guard(story)
    if not allowed:
        return duplicate(reason)

    outcome = deliver(story)
    if outcome.status is not DeliveryStatus.DELIVERED:
        return outcome

    if outcome.message_id is None:
        return transport_failed("delivery_missing_message_id", retryable=False)

    ledger(story, outcome)
    _remember_current_run_publication(story)
    return outcome


__all__ = ["publish_story"]
