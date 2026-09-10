"""Free-model intelligence layer for quality-first, availability-aware routing.

This module owns model eligibility and ordering. The default production
instance also persists bounded health state so a model/provider that exhausts
quota in one GitHub Actions run is not retried blindly in the next run.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "data" / "llm_health.json"


@dataclass(frozen=True)
class DeploymentHealth:
    """Short-lived health state for one model/provider deployment."""

    failures: int = 0
    disabled_until: float = 0.0
    last_error: str = ""
    last_success: float = 0.0

    @property
    def available(self) -> bool:
        return self.disabled_until <= time.time()


class FreeModelIntelligence:
    """Rank trusted free deployments and maintain bounded health state."""

    def __init__(self, state_path: str | Path | None = None, *, persist: bool | None = None) -> None:
        self._health: dict[str, DeploymentHealth] = {}
        self._provider_health: dict[str, DeploymentHealth] = {}
        self._lock = threading.RLock()
        self._state_path = Path(state_path) if state_path else None
        self._persist = bool(persist) if persist is not None else bool(state_path)
        if self._persist:
            self._state_path = self._state_path or DEFAULT_STATE_PATH
            self._load_state()

    def _load_state(self) -> None:
        path = self._state_path
        if path is None:
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(raw, dict):
            return
        self._health = self._decode_section(raw.get("models"))
        self._provider_health = self._decode_section(raw.get("providers"))

    @staticmethod
    def _decode_section(value) -> dict[str, DeploymentHealth]:
        if not isinstance(value, dict):
            return {}
        now = time.time()
        result: dict[str, DeploymentHealth] = {}
        for key, row in value.items():
            if not isinstance(row, dict):
                continue
            try:
                until = float(row.get("disabled_until", 0.0) or 0.0)
                failures = max(0, int(row.get("failures", 0) or 0))
                last_success = float(row.get("last_success", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            # Expired entries are harmless but need not remain in the file.
            if until <= now and not row.get("last_error"):
                continue
            result[str(key)] = DeploymentHealth(
                failures=failures,
                disabled_until=until,
                last_error=str(row.get("last_error", ""))[:500],
                last_success=last_success,
            )
        return result

    def _save_state(self) -> None:
        if not self._persist or self._state_path is None:
            return
        path = self._state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()

        def encode(section: dict[str, DeploymentHealth]) -> dict:
            result = {}
            for key, health in section.items():
                if health.disabled_until <= now and not health.last_error and not health.last_success:
                    continue
                result[key] = {
                    "failures": health.failures,
                    "disabled_until": round(health.disabled_until, 3),
                    "last_error": health.last_error[:500],
                    "last_success": round(health.last_success, 3),
                }
            return result

        payload = {
            "version": 1,
            "updated_at": time.time(),
            "models": encode(self._health),
            "providers": encode(self._provider_health),
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def health(self, deployment_id: str) -> DeploymentHealth:
        with self._lock:
            return self._health.get(deployment_id, DeploymentHealth())

    def provider_health(self, provider_family: str) -> DeploymentHealth:
        with self._lock:
            return self._provider_health.get(str(provider_family or "").strip().casefold(), DeploymentHealth())

    def mark_success(self, deployment_id: str) -> None:
        with self._lock:
            self._health[deployment_id] = DeploymentHealth(
                failures=0,
                disabled_until=0.0,
                last_error="",
                last_success=time.time(),
            )
            self._save_state()

    def mark_failure(
        self,
        deployment_id: str,
        reason: str,
        cooldown_seconds: float,
        *,
        provider_family: str | None = None,
        provider_scope: bool = False,
    ) -> None:
        with self._lock:
            now = time.time()
            old = self._health.get(deployment_id, DeploymentHealth())
            self._health[deployment_id] = DeploymentHealth(
                failures=old.failures + 1,
                disabled_until=max(old.disabled_until, now + max(0.0, float(cooldown_seconds))),
                last_error=str(reason)[:500],
                last_success=old.last_success,
            )
            if provider_scope and provider_family:
                family = str(provider_family).strip().casefold()
                old_provider = self._provider_health.get(family, DeploymentHealth())
                self._provider_health[family] = DeploymentHealth(
                    failures=old_provider.failures + 1,
                    disabled_until=max(old_provider.disabled_until, now + max(0.0, float(cooldown_seconds))),
                    last_error=str(reason)[:500],
                    last_success=old_provider.last_success,
                )
            self._save_state()

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
        """Return currently usable deployments, quality first.

        Availability is a hard gate. Both deployment-level and provider-family
        health are checked before quality ordering is applied.
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
            family = str(entry.get("family") or "").strip().casefold()
            if family and self.provider_health(family).available is False:
                continue
            row = dict(entry)
            row["deployment_id"] = deployment_id
            row["availability"] = "available"
            usable.append(row)
        usable.sort(key=lambda x: (-self._quality(x), self._priority(x), str(x.get("id", ""))))
        return usable


_DEFAULT_INTELLIGENCE = FreeModelIntelligence(DEFAULT_STATE_PATH, persist=True)


def get_intelligence() -> FreeModelIntelligence:
    return _DEFAULT_INTELLIGENCE
