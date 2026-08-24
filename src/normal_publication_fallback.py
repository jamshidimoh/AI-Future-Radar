"""Compatibility wrapper for the normal publication policy.

The wrapper may track successful delivery, but it never converts a policy block
into a synthetic delivery. Publication quality remains authoritative.
"""
from __future__ import annotations

from typing import Any, Callable

from src.delivery_contract import DeliveryOutcome

_NORMAL_DELIVERED = 0


def wrap_policy(
    policy: Callable[[dict[str, Any]], DeliveryOutcome],
    ledger: Callable[[dict[str, Any], DeliveryOutcome], None],
    *,
    rank_window: int = 4,
) -> tuple[Callable[[dict[str, Any]], DeliveryOutcome], Callable[[dict[str, Any], DeliveryOutcome], None]]:
    """Preserve the production policy while tracking actual normal deliveries.

    ``rank_window`` is retained for API compatibility. There is intentionally
    no score-policy bypass here: a blocked story must remain blocked.
    """
    def tracked_ledger(story: dict[str, Any], outcome: DeliveryOutcome) -> None:
        global _NORMAL_DELIVERED
        ledger(story, outcome)
        if outcome.message_id is not None and story.get("content_type") != "education" and story.get("normal_period_rank") is not None:
            _NORMAL_DELIVERED += 1

    def strict_policy(story: dict[str, Any]) -> DeliveryOutcome:
        return policy(story)

    return strict_policy, tracked_ledger
