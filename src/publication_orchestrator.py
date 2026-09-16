"""Single Story-to-Publication orchestration boundary.

This module owns the decision boundary between editorial policy, transport,
and the publication ledger. Callers provide the concrete policy, delivery,
and ledger functions; lower layers must not make publication decisions.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from src.delivery_contract import DeliveryOutcome, DeliveryStatus, duplicate, transport_failed
from src.rejection_telemetry import build_event, emit

logger = logging.getLogger(__name__)

Policy = Callable[[Mapping[str, Any]], DeliveryOutcome]
Deliver = Callable[[Mapping[str, Any]], DeliveryOutcome]
Ledger = Callable[[Mapping[str, Any], DeliveryOutcome], None]

_CURRENT_RUN_PUBLICATIONS: list[dict[str, Any]] = []


def _telemetry_event(story: Mapping[str, Any], *, decision: str, reason_code: str, details=None) -> None:
    try:
        identity = str(story.get("canonical_url") or story.get("link") or story.get("url") or story.get("title") or id(story))
        import hashlib
        trace_id = hashlib.sha1(identity.encode("utf-8", errors="ignore")).hexdigest()[:16]
        raw_run_number = os.getenv("GITHUB_RUN_NUMBER") or os.getenv("RADAR_RUN_NUMBER")
        try:
            run_number = int(raw_run_number) if raw_run_number is not None else None
        except (TypeError, ValueError):
            run_number = None
        emit(
            build_event(
                run_id=str(os.getenv("GITHUB_RUN_ID") or os.getenv("RADAR_RUN_ID") or "local"),
                run_number=run_number,
                trace_id=trace_id,
                item_id=identity,
                stage="publication_contract",
                decision=decision,
                reason_code=reason_code,
                item=story,
                details=details,
            ),
            Path(os.getenv("RADAR_REJECTION_TRACE_PATH", "artifacts/rejection_trace/rejection_trace.jsonl")),
        )
    except Exception:
        return


def _publication_reason_code(reason: str | None) -> str:
    value = str(reason or "").strip()
    if value.startswith("normal_score_policy_blocked:"):
        return "normal_score_floor"
    if value.startswith("tier0_score_policy_blocked:"):
        return "protected_score_floor"
    if value == "normal_quota_exhausted":
        return "publication_quota_exhausted"
    if value == "normal_rank_outside_window" or value.startswith("normal_rank_outside_window:"):
        return "normal_rank_outside_window"
    if value == "strategic_analytical_lane_exhausted":
        return "strategic_analytical_lane_exhausted"
    if value == "news_language_gate":
        return "language_gate_failure"
    if value == "publication_guard_unavailable":
        return "publication_guard_unavailable"
    return "publication_policy_rejection"


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
        logger.error("Final publication guard unavailable: %s", exc, exc_info=True)
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
        reason = str(decision.reason or "")
        _telemetry_event(
            story,
            decision="reject",
            reason_code=_publication_reason_code(reason),
            details={"status": decision.status.value, "policy_reason": reason},
        )
        return decision

    if decision.status is not DeliveryStatus.DELIVERED and decision.message_id is not None:
        _telemetry_event(
            story,
            decision="reject",
            reason_code="invalid_policy_outcome",
            details={"status": decision.status.value},
        )
        return transport_failed("invalid_policy_outcome", retryable=False)

    allowed, reason = _final_story_guard(story)
    if not allowed:
        _telemetry_event(
            story,
            decision="reject",
            reason_code=_publication_reason_code(reason),
            details={"guard_reason": reason},
        )
        return duplicate(reason)

    outcome = deliver(story)
    if outcome.status is not DeliveryStatus.DELIVERED:
        return outcome

    if outcome.message_id is None:
        _telemetry_event(
            story,
            decision="reject",
            reason_code="delivery_missing_message_id",
            details={"status": outcome.status.value},
        )
        return transport_failed("delivery_missing_message_id", retryable=False)

    ledger(story, outcome)
    _remember_current_run_publication(story)
    return outcome


__all__ = ["publish_story"]
