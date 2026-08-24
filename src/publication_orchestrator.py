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


def publish_story(
    story: Mapping[str, Any],
    *,
    policy: Policy,
    deliver: Deliver,
    ledger: Ledger,
) -> DeliveryOutcome:
    """Execute exactly one publication attempt for one Story.

    Policy rejection never reaches transport. Transport failure never reaches
    the ledger. The ledger is called only after a confirmed Telegram
    ``message_id`` is present in a DELIVERED outcome.
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

    outcome = deliver(story)
    if outcome.status is not DeliveryStatus.DELIVERED:
        return outcome

    if outcome.message_id is None:
        return transport_failed("delivery_missing_message_id", retryable=False)

    ledger(story, outcome)
    return outcome


__all__ = ["publish_story"]
