"""Refresh the runtime free-model registry from current provider metadata.

Discovery is deliberately separated from trust ranking. Live catalogs validate
free/available models; quality evidence is carried into runtime metadata and is
used by the quality-first selector. Unknown candidates remain quarantined.
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


def _kira_models(token: str | None) -> tuple[bool, dict[str, dict], str]:
    if not token:
        return False, {}, "missing credential"
    status, payload = _get_json("https://kiraai.vn/api/v1/models", token=token)
    if status in (401, 403):
        return False, {}, f"authentication failed HTTP {status}"
    if status >= 400:
        return False, {}, f"model catalog failed HTTP {status}"
    rows = payload.get("data") or []
    return True, {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}, "catalog ok"


def _is_zero_price(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    try:
        return float(pricing.get("prompt", pricing.get("input", "-1"))) == 0 and float(pricing.get("completion", pricing.get("output", "-1"))) == 0
    except (TypeError, ValueError):
        return False


def _supports_response_format(model: dict) -> bool:
    supported = model.get("supported_parameters") or []
    return "response_format" in {str(x).strip() for x in supported}


def _known_quality(model_id: str) -> tuple[float, float, str]:
    """Return conservative quality/task-fit evidence and its provenance."""
    key = model_id.lower()
    overrides = {
        "gpt-5.6-luna-free": (0, 0, "unverified"),
        "minimax-m3-free": (94, 96, "independent"),
        "dots-3-note-preview": (72, 82, "independent"),
        "nvidia/nemotron-3-ultra-550b-a55b:free": (98, 94, "independent"),
        "nvidia/nemotron-3-super-120b-a12b:free": (97, 94, "independent"),
        "openai/gpt-oss-120b:free": (94, 97, "independent"),
    }
    return overrides.get(key, (0, 0, "unverified"))


def _conservative_quality(model: dict, base_quality: float, task_fit: float, evidence: str) -> tuple[float, float]:
    if evidence == "provider_only":
        # Provider marketing establishes availability, not comparative quality.
        return min(float(base_quality), 84.0), min(float(task_fit), 89.0)
    return float(base_quality), float(task_fit)


def refresh() -> dict:
    static = _load_static()
    registry = copy.deepcopy(static["registry"])
    openrouter_token = os.getenv("OPENROUTER_API_KEY")
    groq_token = os.getenv("GROQ_API_KEY")
    kira_token = os.getenv("KIRAAI_API_KEY")
    or_auth_ok, or_auth_reason = _openrouter_auth(openrouter_token)
    or_models, or_catalog_reason = _openrouter_models(openrouter_token)
    groq_ok, groq_models, groq_reason = _groq_models(groq_token)
    kira_ok, kira_models, kira_reason = _kira_models(kira_token)
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
        elif family == "kiraai":
            provider["credential_valid"] = kira_ok
            provider["validation"] = kira_reason
            catalog = kira_models
        else:
            env_name = str(provider.get("credential_env") or "").strip()
            provider["credential_valid"] = bool(env_name and os.getenv(env_name))
            provider["validation"] = "credential presence only"
            catalog = {}

        for model in provider.get("models", []) or []:
            model_id = str(model.get("id", ""))
            live = catalog.get(model_id)
            model["enabled"] = True
            if family in {"openrouter", "kiraai"}:
                if not live or not provider["credential_valid"]:
                    model["enabled"] = False
                    model["runtime_reason"] = "provider_unavailable"
                else:
                    if family == "openrouter":
                        model["free"] = _is_zero_price(live)
                    else:
                        model["free"] = bool(model.get("free") is True)
                    model["context_length"] = int(live.get("context_length") or 0)
                    model["response_format"] = _supports_response_format(live) or bool(model.get("response_format"))
                    if not model["free"]:
                        model["enabled"] = False
                        model["runtime_reason"] = "not_free"
            elif family == "groq" and not live:
                model["enabled"] = False
                model["runtime_reason"] = "not_listed"

            if model.get("quality_evidence") == "provider_only":
                model["base_quality"], model["task_fit"] = _conservative_quality(model, model.get("base_quality", 0), model.get("task_fit", 0), "provider_only")
                model["quality_score"] = round(float(model["base_quality"]) * 0.80 + float(model["task_fit"]) * 0.20, 3)

    trusted_ids = {str(m.get("id")) for p in registry.get("providers", []) for m in p.get("models", [])}
    for family, catalog in (("openrouter", or_models), ("kiraai", kira_models)):
        for model_id, live in sorted(catalog.items()):
            if model_id in trusted_ids:
                continue
            free = _is_zero_price(live) if family == "openrouter" else model_id.endswith("-free")
            if not free:
                continue
            base_quality, task_fit, evidence = _known_quality(model_id)
            if base_quality <= 0:
                continue
            discovery.append({
                "id": model_id,
                "family": family,
                "free": True,
                "chat_capable": True,
                "json_capable": True,
                "response_format": _supports_response_format(live),
                "context_length": int(live.get("context_length") or 0),
                "base_quality": base_quality,
                "task_fit": task_fit,
                "quality_score": round(base_quality * 0.80 + task_fit * 0.20, 3),
                "quality_evidence": evidence,
                "priority": 1000,
                "promotion_status": "candidate_with_quality_evidence",
            })
    discovery.sort(key=lambda x: (-x["quality_score"], x["id"]))

    runtime = {
        "runtime": {
            "schema_version": 3,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "discovery_candidates": discovery[:30],
            "provider_validation": {
                "openrouter": {"valid": or_auth_ok, "reason": f"{or_auth_reason}; {or_catalog_reason}"},
                "groq": {"valid": groq_ok, "reason": groq_reason},
                "kiraai": {"valid": kira_ok, "reason": kira_reason},
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
    parser.add_argument("--strict", action="store_true", help="fail when no core provider validates")
    args = parser.parse_args()
    runtime = refresh()
    validation = runtime["runtime"]["provider_validation"]
    if args.strict and not any(validation[name]["valid"] for name in ("groq", "openrouter", "kiraai")):
        raise SystemExit("No core production provider credential validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
