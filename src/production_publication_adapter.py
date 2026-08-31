"""Production adapter: keeps legacy editorial hooks out of the publication boundary."""
from __future__ import annotations

from typing import Any, Callable

from src.delivery_contract import DeliveryOutcome, from_legacy
from src.publication_orchestrator import publish_story


def publish_production_story(
    story: dict[str, Any],
    *,
    policy: Callable[[dict[str, Any]], DeliveryOutcome],
    transport: Callable[[dict[str, Any]], object],
    ledger: Callable[[dict[str, Any], DeliveryOutcome], None],
) -> DeliveryOutcome:
    """Single production Story→Publication boundary.

    The transport adapter is the only callable allowed to talk to Telegram.
    Legacy transport results are normalized before the Ledger boundary.
    """
    def deliver(item: dict[str, Any]) -> DeliveryOutcome:
        result = transport(item)
        return from_legacy(result)

    return publish_story(
        story,
        policy=policy,
        deliver=deliver,
        ledger=ledger,
    )
