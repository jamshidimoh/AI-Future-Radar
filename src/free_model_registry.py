"""Deterministic production ordering for trusted free LLM models.

The registry is curated for AI Future Radar and refreshed externally. Runtime
selection never samples a provider/model at random: it filters by credential,
health state and required capabilities, then follows the stored priority.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "free_model_registry.yaml"


def _load():
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}


def _healthy(model: dict) -> bool:
    return model.get("enabled", True) is not False and model.get("health", "healthy") != "disabled"


def ranked_entries() -> list[dict]:
    data = _load().get("registry", {})
    entries: list[dict] = []
    for provider in data.get("providers", []):
        family = str(provider.get("family", "")).strip().lower()
        credential_env = provider.get("credential_env")
        for model in provider.get("models", []) or []:
            if not isinstance(model, dict) or not model.get("id") or not _healthy(model):
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

    OpenRouter models remain individual candidates, while OpenRouter itself is
    responsible for provider-level failover behind each model endpoint.
    Gemini stays optional and non-authoritative; Hugging Face stays the final
    emergency lane because its free-user credit is intentionally limited.
    """
    chain = []
    for entry in ranked_entries():
        family = entry["family"]
        model_id = entry["id"]
        if family == "groq":
            fn = lambda sp, uc, m=model_id: router._groq(sp, uc, m)
        elif family == "openrouter":
            fn = lambda sp, uc, m=model_id: router._openrouter(sp, uc, m)
        else:
            continue
        chain.append((f"{family.title()}:{model_id}", fn))

    # Gemini is retained only when explicitly configured and after the curated
    # free-model pool. It must never become the sole production dependency.
    chain.append(("Gemini", router._gemini))
    chain.append(("HuggingFace", router._huggingface))
    return chain
