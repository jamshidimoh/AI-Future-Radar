"""Refresh the runtime free-model registry from current provider metadata.

Discovery/validation only: the canonical trust list is never rewritten here.
OpenRouter model metadata is public, while GET /api/v1/key validates the actual
configured credential. Groq's authenticated model catalog validates its key
without consuming inference quota.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
STATIC_PATH = ROOT / "config" / "free_model_registry.yaml"
RUNTIME_PATH = ROOT / "artifacts" / "free_model_registry.runtime.yaml"
TIMEOUT = 12


def _load_static() -> dict:
    value = yaml.safe_load(STATIC_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict) or not isinstance(value.get("registry"), dict):
        raise RuntimeError("Invalid canonical model registry")
    return value


def _get_json(url: str, *, token: str | None = None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(url, headers=headers, timeout=TIMEOUT)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, payload if isinstance(payload, dict) else {}


def _openrouter_auth(token: str | None) -> tuple[bool, str]:
    if not token:
        return False, "missing credential"
    status, _payload = _get_json("https://openrouter.ai/api/v1/key", token=token)
    if status == 401:
        return False, "authentication failed HTTP 401"
    if status == 403:
        return False, "credential forbidden HTTP 403"
    if status >= 400:
        return False, f"credential validation failed HTTP {status}"
    return True, "credential valid"


def _openrouter_models(token: str | None) -> tuple[dict[str, dict], str]:
    status, payload = _get_json("https://openrouter.ai/api/v1/models", token=token)
    if status >= 400:
        return {}, f"model catalog failed HTTP {status}"
    rows = payload.get("data") or []
    return {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}, "catalog ok"


def _groq_models(token: str | None) -> tuple[bool, dict[str, dict], str]:
    if not token:
        return False, {}, "missing credential"
    status, payload = _get_json("https://api.groq.com/openai/v1/models", token=token)
    if status in (401, 403):
        return False, {}, f"authentication failed HTTP {status}"
    if status >= 400:
        return False, {}, f"model catalog failed HTTP {status}"
    rows = payload.get("data") or []
    return True, {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}, "catalog ok"


def _is_zero_price(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    try:
        return float(pricing.get("prompt", "-1")) == 0 and float(pricing.get("completion", "-1")) == 0
    except (TypeError, ValueError):
        return False


def _supports_response_format(model: dict) -> bool:
    supported = model.get("supported_parameters") or []
    return "response_format" in {str(x).strip() for x in supported}


def refresh() -> dict:
    static = _load_static()
    registry = copy.deepcopy(static["registry"])
    openrouter_token = os.getenv("OPENROUTER_API_KEY")
    or_auth_ok, or_auth_reason = _openrouter_auth(openrouter_token)
    or_models, or_catalog_reason = _openrouter_models(openrouter_token)
    groq_ok, groq_models, groq_reason = _groq_models(os.getenv("GROQ_API_KEY"))
    discovery: list[dict] = []

    for provider in registry.get("providers", []) or []:
        family = str(provider.get("family", "")).strip().lower()
        if family == "openrouter":
            provider["credential_valid"] = or_auth_ok
            provider["validation"] = f"{or_auth_reason}; {or_catalog_reason}"
            catalog = or_models
        elif family == "groq":
            provider["credential_valid"] = groq_ok
            provider["validation"] = groq_reason
            catalog = groq_models
        else:
            env_name = str(provider.get("credential_env") or "").strip()
            provider["credential_valid"] = bool(env_name and os.getenv(env_name))
            provider["validation"] = "credential presence only"
            catalog = {}

        for model in provider.get("models", []) or []:
            model_id = str(model.get("id", ""))
            live = catalog.get(model_id)
            model["enabled"] = True
            if family == "openrouter":
                if not live or not or_auth_ok:
                    model["enabled"] = False
                    model["runtime_reason"] = "provider_unavailable"
                else:
                    model["free"] = _is_zero_price(live)
                    model["context_length"] = int(live.get("context_length") or 0)
                    model["response_format"] = _supports_response_format(live)
                    if not model["free"]:
                        model["enabled"] = False
                        model["runtime_reason"] = "not_free"
            elif family == "groq" and not live:
                model["enabled"] = False
                model["runtime_reason"] = "not_listed"

    if or_models:
        trusted_ids = {str(m.get("id")) for p in registry.get("providers", []) for m in p.get("models", [])}
        for model_id, live in sorted(or_models.items()):
            if model_id in trusted_ids or not model_id.endswith(":free") or not _is_zero_price(live):
                continue
            modality = str((live.get("architecture") or {}).get("modality") or "").lower()
            if "text->text" not in modality and modality and "text" not in modality:
                continue
            discovery.append({
                "id": model_id,
                "family": "openrouter",
                "free": True,
                "chat_capable": True,
                "json_capable": True,
                "response_format": _supports_response_format(live),
                "context_length": int(live.get("context_length") or 0),
                "priority": 1000,
                "promotion_status": "candidate_only",
            })
        discovery = discovery[:20]

    runtime = {
        "runtime": {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "discovery_candidates": discovery,
            "provider_validation": {
                "openrouter": {"valid": or_auth_ok, "reason": or_auth_reason},
                "groq": {"valid": groq_ok, "reason": groq_reason},
            },
        },
        "registry": registry,
    }
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PATH.write_text(yaml.safe_dump(runtime, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(json.dumps(runtime["runtime"], ensure_ascii=False, indent=2), flush=True)
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="fail when no credentialed core provider validates")
    args = parser.parse_args()
    runtime = refresh()
    validation = runtime["runtime"]["provider_validation"]
    if args.strict and not (validation["groq"]["valid"] or validation["openrouter"]["valid"]):
        raise SystemExit("No core production provider credential validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
