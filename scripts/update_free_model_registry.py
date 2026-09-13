"""Refresh the trusted free-model registry from current provider catalogs.

This updater is deliberately conservative: it may add only general-purpose
free chat models that expose structured-output capability, and it never changes
Groq's curated production list automatically. OpenRouter discovery is public;
no paid account is required for catalog inspection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "free_model_registry.yaml"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

BLOCKED = ("embed", "rerank", "speech", "audio", "image", "video", "code")
PREFERRED_PREFIXES = (
    "nvidia/nemotron-",
    "google/gemma-4",
    "openai/gpt-oss-",
    "qwen/",
    "deepseek/",
    "mistralai/",
)


def _free(item: dict) -> bool:
    pricing = item.get("pricing") or {}
    try:
        return float(pricing.get("prompt", "1")) == 0 and float(pricing.get("completion", "1")) == 0
    except (TypeError, ValueError):
        return False


def _chat_capable(item: dict) -> bool:
    arch = item.get("architecture") or {}
    modalities = {str(x).lower() for x in (arch.get("input_modalities") or [])}
    return "text" in modalities and "text" in {str(x).lower() for x in (arch.get("output_modalities") or ["text"])}


def _structured(item: dict) -> bool:
    params = {str(x).lower() for x in (item.get("supported_parameters") or [])}
    return bool({"response_format", "structured_outputs"} & params)


def _general_purpose(item: dict) -> bool:
    model_id = str(item.get("id") or "").lower()
    name = str(item.get("name") or "").lower()
    return not any(token in model_id or token in name for token in BLOCKED)


def _freshness_score(created) -> float:
    if not created:
        return 40.0
    try:
        days = max(0.0, (datetime.now(timezone.utc) - datetime.fromtimestamp(float(created), tz=timezone.utc)).total_seconds() / 86400.0)
    except (TypeError, ValueError, OverflowError):
        return 40.0
    return max(35.0, min(100.0, 100.0 - days * 0.10))


def _candidate_score(item: dict) -> float:
    context = min(100.0, float(item.get("context_length") or 0) / 8192.0)
    providers = min(100.0, float((item.get("top_provider") or {}).get("max_completion_tokens") or 0) / 1024.0)
    freshness = _freshness_score(item.get("created"))
    preferred = 8.0 if str(item.get("id") or "").lower().startswith(PREFERRED_PREFIXES) else 0.0
    structured = 15.0 if _structured(item) else 0.0
    return structured + 0.25 * context + 0.05 * providers + 0.40 * freshness + preferred


def refresh() -> int:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    registry = data.setdefault("registry", {})
    providers = registry.setdefault("providers", [])
    target = next(p for p in providers if p.get("family") == "openrouter")
    current = {m["id"]: m for m in target.get("models", []) or [] if isinstance(m, dict) and m.get("id")}

    response = requests.get(OPENROUTER_MODELS_URL, timeout=20)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", []) if isinstance(payload, dict) else []

    discovered = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "")
        if not model_id.endswith(":free") or not _free(item) or not _chat_capable(item) or not _structured(item) or not _general_purpose(item):
            continue
        row = dict(current.get(model_id, {}))
        row.update({
            "id": model_id,
            "health": row.get("health", "healthy"),
            "health_score": row.get("health_score", 100),
            "catalog_score": round(_candidate_score(item), 3),
            "verified_at": datetime.now(timezone.utc).isoformat(),
        })
        discovered.append(row)

    keep = {m["id"]: m for m in discovered}
    # Preserve curated models even when the catalog has a temporary metadata gap.
    for model_id, model in current.items():
        if model_id not in keep:
            keep[model_id] = model

    ordered = sorted(
        keep.values(),
        key=lambda m: (-float(m.get("catalog_score", 0)), -float(m.get("base_quality", 0)), m["id"]),
    )
    target["models"] = ordered
    registry["last_refresh"] = datetime.now(timezone.utc).isoformat()
    REGISTRY.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"[Free Model Registry] refreshed openrouter candidates={len(ordered)}")
    return len(ordered)


if __name__ == "__main__":
    raise SystemExit(0 if refresh() >= 1 else 1)
