"""Free-model intelligence layer for quality-first, availability-aware routing.

This module deliberately owns *selection policy* while LiteLLM owns provider
execution. A deployment must first be trusted as free/chat/JSON-capable and
credentialed; only then is quality used to order it. Runtime failures are
recorded in-process so an exhausted deployment is not retried repeatedly in
one Radar run.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DeploymentHealth:
    """Short-lived health state for one model/provider deployment."""

    failures: int = 0
    disabled_until: float = 0.0
    last_error: str = ""
    last_success: float = 0.0

    @property
    def available(self) -> bool:
        return self.disabled_until <= time.monotonic()


class FreeModelIntelligence:
    """Rank trusted free deployments and maintain per-run availability state."""

    def __init__(self) -> None:
        self._health: dict[str, DeploymentHealth] = {}
        self._lock = threading.RLock()

    def health(self, deployment_id: str) -> DeploymentHealth:
        with self._lock:
            return self._health.get(deployment_id, DeploymentHealth())

    def mark_success(self, deployment_id: str) -> None:
        with self._lock:
            self._health[deployment_id] = DeploymentHealth(
                failures=0,
                disabled_until=0.0,
                last_error="",
                last_success=time.monotonic(),
            )

    def mark_failure(self, deployment_id: str, reason: str, cooldown_seconds: float) -> None:
        with self._lock:
            old = self._health.get(deployment_id, DeploymentHealth())
            self._health[deployment_id] = DeploymentHealth(
                failures=old.failures + 1,
                disabled_until=max(old.disabled_until, time.monotonic() + cooldown_seconds),
                last_error=str(reason)[:500],
                last_success=old.last_success,
            )

    @staticmethod
    def _quality(entry: dict) -> float:
        try:
            return float(entry.get("quality_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _priority(entry: dict) -> int:
        try:
            return int(entry.get("priority", 9999) or 9999)
        except (TypeError, ValueError):
            return 9999

    def rank(self, entries: Iterable[dict]) -> list[dict]:
        """Return only currently usable deployments, quality first.

        Availability is a hard gate, not a small score bonus: a higher-quality
        deployment that is currently rate-limited must never outrank a usable
        deployment because it is unavailable.
        """
        usable: list[dict] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("free") is not True:
                continue
            if entry.get("chat_capable") is not True:
                continue
            if entry.get("json_capable") is not True:
                continue
            deployment_id = str(entry.get("deployment_id") or entry.get("id") or "").strip()
            if not deployment_id or self.health(deployment_id).available is False:
                continue
            row = dict(entry)
            row["deployment_id"] = deployment_id
            row["availability"] = "available"
            usable.append(row)
        usable.sort(key=lambda x: (-self._quality(x), self._priority(x), str(x.get("id", ""))))
        return usable


_DEFAULT_INTELLIGENCE = FreeModelIntelligence()


def get_intelligence() -> FreeModelIntelligence:
    return _DEFAULT_INTELLIGENCE
