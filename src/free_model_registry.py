"""Deterministic production ordering for trusted free LLM models.

The registry is curated for AI Future Radar and refreshed externally. Runtime
selection never samples a provider/model at random: it filters by credential,
health state and required capabilities, then follows the stored priority.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "free_model_registry.yaml"


def _load():
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}


def _healthy(model: dict) -> bool:
    return model.get("enabled", True) is not False and model.get("health", "healthy") != "disabled"


def _credential_available(env_name: str | None) -> bool:
    return bool(env_name and os.getenv(str(env_name).strip()))


def ranked_entries() -> list[dict]:
    data = _load().get("registry", {})
    entries: list[dict] = []
    for provider in data.get("providers", []):
        family = str(provider.get("family", "")).strip().lower()
        credential_env = provider.get("credential_env")
        for model in provider.get("models", []) or []:
            if not isinstance(model, dict) or not model.get("id") or not _healthy(model):
                continue
            if credential_env and not _credential_available(credential_env):
                continue
            row = dict(model)
            row["family"] = family
            row["credential_env"] = credential_env
            row["effective_score"] = (
                0.55 * float(row.get("base_quality", 0))
                + 0.20 * float(row.get("task_fit", 0))
                + 0.10 * float(row.get("freshness", 0))
                + 0.15 * float(row.get("health_score", 100))
            )
            entries.append(row)
    entries.sort(key=lambda x: (-x["effective_score"], -float(x.get("base_quality", 0)), x["id"]))
    return entries


def build_production_chain(router):
    """Return production providers in deterministic quality-first order.

    The registry is the single production model-selection authority. Runtime
    state may temporarily cool down individual models, but it never reorders
    healthy candidates randomly or disables siblings because one model failed.
    """
    data = _load().get("registry", {})
    max_runtime_candidates = int(data.get("max_runtime_candidates", 10) or 10)
    require_free = bool(data.get("require_free", True))
    require_chat = bool(data.get("require_chat", True))
    require_structured = bool(data.get("require_structured_output", True))

    chain = []
    for entry in ranked_entries():
        if require_free and entry.get("free") is False:
            continue
        if require_chat and entry.get("chat_capable") is False:
            continue
        if require_structured and entry.get("structured_output") is False:
            continue
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

    # Gemini is retained only as an optional emergency lane after all curated
    # free models. Hugging Face remains the final lane because its free-user
    # credit is explicitly limited.
    if _credential_available("GEMINI_API_KEY"):
        chain.append(("Gemini", router._gemini))
    if _credential_available("HF_TOKEN"):
        chain.append(("HuggingFace", router._huggingface))

    if not chain:
        raise RuntimeError("No credentialed production LLM model is available")
    return chain
