"""Typed delivery outcomes for the single Story-to-Publication boundary."""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any


class DeliveryStatus(str, Enum):
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    POLICY_BLOCKED = "policy_blocked"
    DELIVERY_FAILED_RETRYABLE = "delivery_failed_retryable"
    DELIVERY_FAILED_PERMANENT = "delivery_failed_permanent"
    DELIVERED = "delivered"


@dataclass(frozen=True)
class DeliveryOutcome:
    status: DeliveryStatus
    reason: str = ""
    message_id: int | None = None
    chat_id: int | str | None = None
    http_status: int | None = None
    telegram_error_code: int | None = None
    telegram_description: str = ""
    retryable: bool = False

    @property
    def ok(self) -> bool:
        return self.status is DeliveryStatus.DELIVERED and self.message_id is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status.value,
            "reason": self.reason,
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "http_status": self.http_status,
            "telegram_error_code": self.telegram_error_code,
            "telegram_description": self.telegram_description,
            "retryable": self.retryable,
        }


def delivered(meta: dict[str, Any]) -> DeliveryOutcome:
    return DeliveryOutcome(DeliveryStatus.DELIVERED, reason="published", message_id=meta.get("message_id"), chat_id=meta.get("chat_id"))


def rejected(reason: str) -> DeliveryOutcome:
    return DeliveryOutcome(DeliveryStatus.REJECTED, reason=reason)


def duplicate(reason: str) -> DeliveryOutcome:
    return DeliveryOutcome(DeliveryStatus.DUPLICATE, reason=reason)


def policy_blocked(reason: str) -> DeliveryOutcome:
    return DeliveryOutcome(DeliveryStatus.POLICY_BLOCKED, reason=reason)


def transport_failed(reason: str, *, retryable: bool, http_status: int | None = None, telegram_error_code: int | None = None, telegram_description: str = "") -> DeliveryOutcome:
    return DeliveryOutcome(
        status=DeliveryStatus.DELIVERY_FAILED_RETRYABLE if retryable else DeliveryStatus.DELIVERY_FAILED_PERMANENT,
        reason=reason,
        http_status=http_status,
        telegram_error_code=telegram_error_code,
        telegram_description=telegram_description,
        retryable=retryable,
    )


def from_legacy(result: object, *, guard_reason: str = "") -> DeliveryOutcome:
    """Convert legacy transport results without collapsing known guard failures."""
    if isinstance(result, DeliveryOutcome):
        return result
    if isinstance(result, dict):
        if result.get("message_id") is not None:
            return delivered(result)
        status = str(result.get("status") or "").strip().lower()
        reason = str(result.get("reason") or guard_reason or "telegram_delivery_failed")
        if status == DeliveryStatus.DUPLICATE.value:
            return duplicate(reason)
        if status == DeliveryStatus.POLICY_BLOCKED.value:
            return policy_blocked(reason)
        if status == DeliveryStatus.REJECTED.value:
            return rejected(reason)
        return transport_failed(reason, retryable=bool(result.get("retryable", False)), http_status=result.get("http_status"), telegram_error_code=result.get("telegram_error_code"), telegram_description=str(result.get("telegram_description") or ""))
    env_reason = str(os.environ.get("AI_RADAR_PUBLICATION_GUARD_REASON") or "").strip()
    if env_reason:
        return duplicate(env_reason)
    return transport_failed(guard_reason or "telegram_delivery_failed", retryable=False)
