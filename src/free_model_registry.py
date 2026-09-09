"""Deterministic production ordering for trusted free LLM models.

The canonical trust list is explicit and auditable. A separate runtime registry
may validate availability/capabilities, but it cannot silently invent a new
production priority order. Discovery candidates remain quarantined until they
are promoted into the trust list.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "free_model_registry.yaml"
RUNTIME_REGISTRY_PATH = ROOT / "artifacts" / "free_model_registry.runtime.yaml"


def _read(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return value if isinstance(value, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def _runtime_is_fresh(data: dict) -> bool:
    meta = data.get("runtime", {}) if isinstance(data, dict) else {}
    stamp = str(meta.get("generated_at", "")).strip()
    if not stamp:
        return False
    try:
        generated = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    age_hours = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 3600.0
    stale_after = float(data.get("registry", {}).get("stale_after_hours", 72) or 72)
    return 0 <= age_hours <= stale_after


def _load() -> dict:
    runtime = _read(RUNTIME_REGISTRY_PATH)
    if _runtime_is_fresh(runtime) and isinstance(runtime.get("registry"), dict):
        return runtime
    return _read(REGISTRY_PATH)


def _credential_available(env_name: str | None, env: dict[str, str] | None = None) -> bool:
    import os

    source = env if env is not None else os.environ
    return bool(env_name and source.get(str(env_name).strip()))


def _provider_runtime_available(provider: dict) -> bool:
    if provider.get("credential_valid") is False:
        return False
    return True


def canonical_entries() -> list[dict]:
    data = _load().get("registry", {})
    rows: list[dict] = []
    for provider in data.get("providers", []) or []:
        family = str(provider.get("family", "")).strip().lower()
        credential_env = provider.get("credential_env")
        if not _credential_available(credential_env):
            continue
        if not _provider_runtime_available(provider):
            continue
        for model in provider.get("models", []) or []:
            if not isinstance(model, dict):
                continue
            if model.get("enabled", True) is False:
                continue
            if int(model.get("priority", 9999)) >= 1000:
                continue
            if not model.get("id"):
                continue
            if data.get("require_free", True) and model.get("free") is not True:
                continue
            if data.get("require_chat", True) and model.get("chat_capable") is not True:
                continue
            if data.get("require_json_capability", True) and model.get("json_capable") is not True:
                continue
            row = dict(model)
            row["family"] = family
            row["credential_env"] = credential_env
            rows.append(row)
    rows.sort(key=lambda x: (int(x.get("priority", 9999)), x["id"]))
    return rows


def discovered_candidates() -> list[dict]:
    data = _load().get("runtime", {})
    rows = data.get("discovery_candidates", []) if isinstance(data, dict) else []
    return list(rows) if isinstance(rows, list) else []


def model_capability(model_id: str) -> dict:
    for entry in canonical_entries():
        if entry.get("id") == model_id:
            return entry
    for entry in discovered_candidates():
        if entry.get("id") == model_id:
            return entry
    return {}


def build_production_chain(router):
    """Build the canonical production chain without score-based reordering."""
    data = _load().get("registry", {})
    max_runtime_candidates = int(data.get("max_runtime_candidates", 11) or 11)
    chain: list[tuple[str, object]] = []

    for entry in canonical_entries():
        family = entry["family"]
        model_id = entry["id"]
        if family == "groq":
            fn = lambda sp, uc, m=model_id: router._groq(sp, uc, m)
        elif family == "openrouter":
            fn = lambda sp, uc, m=model_id: router._openrouter(sp, uc, m)
        else:
            continue
        display_family = "OpenRouter" if family == "openrouter" else family.title()
        chain.append((f"{display_family}:{model_id}", fn))
        if len(chain) >= max_runtime_candidates:
            break

    # Optional emergency lanes. They are never allowed to outrank the curated
    # canonical list and are opt-in because their quotas/credentials are less
    # predictable for this project.
    import os

    if os.getenv("RADAR_ENABLE_GEMINI_FALLBACK", "0").strip().lower() in {"1", "true", "yes"}:
        if _credential_available("GEMINI_API_KEY"):
            chain.append(("Gemini", router._gemini))
    if os.getenv("RADAR_ENABLE_HF_FALLBACK", "0").strip().lower() in {"1", "true", "yes"}:
        if _credential_available("HF_TOKEN"):
            chain.append(("HuggingFace", router._huggingface))

    if not chain:
        raise RuntimeError("No credentialed trusted production LLM model is available")
    return chain
