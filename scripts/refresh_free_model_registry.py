"""Refresh the free-model registry from live provider and benchmark evidence.

The registry is deliberately evidence-driven. Provider catalogs establish
whether a model is currently reachable and free; OpenRouter benchmark data
provides an independent quality prior when available. Unknown models remain
quarantined until they have enough quality evidence to compete for production.
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


def _get_json(url: str, *, token: str | None = None, query: dict | None = None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(url, headers=headers, params=query or {}, timeout=TIMEOUT)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, payload if isinstance(payload, dict) else {}


def _openrouter_auth(token: str | None) -> tuple[bool, str]:
    if not token:
        return False, "missing credential"
    status, _ = _get_json("https://openrouter.ai/api/v1/key", token=token)
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


def _openrouter_benchmarks(token: str | None) -> tuple[dict[str, dict], str]:
    if not token:
        return {}, "missing credential"
    status, payload = _get_json(
        "https://openrouter.ai/api/v1/benchmarks",
        token=token,
        query={"source": "artificial-analysis", "max_results": 1000},
    )
    if status >= 400:
        return {}, f"benchmark catalog failed HTTP {status}"
    rows = payload.get("data") or []
    from free_model_evidence import benchmark_record

    result: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        evidence = benchmark_record(row)
        model_id = evidence["benchmark_model_id"]
        if not model_id:
            continue
        previous = result.get(model_id)
        if previous is None or evidence.get("intelligence_index", -1) > previous.get("intelligence_index", -1):
            result[model_id] = evidence
    return result, "benchmark catalog ok"


def _openrouter_task_evidence(token: str | None) -> dict[str, float]:
    """Return a small real-world task-fit prior from OpenRouter's 7d taxonomy."""
    if not token:
        return {}
    status, payload = _get_json(
        "https://openrouter.ai/api/v1/classifications/task",
        token=token,
        query={"window": "7d"},
    )
    if status >= 400:
        return {}
    useful = {"summarization", "research", "reports", "q&a", "knowledge", "data extraction", "content writing", "classification"}
    scores: dict[str, float] = {}
    for row in (payload.get("data") or {}).get("classifications", []) if isinstance(payload.get("data"), dict) else []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("display_name") or row.get("tag") or "").strip().lower()
        if not any(term in label for term in useful):
            continue
        for model in row.get("models") or []:
            if not isinstance(model, dict) or not model.get("id"):
                continue
            model_id = str(model["id"]).strip().lower()
            scores[model_id] = max(scores.get(model_id, 0.0), float(model.get("usage_share", 0.0) or 0.0) * 100.0)
    return scores


def _free_llm_router_ids(token: str | None) -> tuple[bool, list[str], str]:
    if not token:
        return False, [], "missing credential"
    status, payload = _get_json(
        "https://freellmrouter.com/api/v1/models/ids",
        token=token,
        query={"useCase": "chat", "sort": "capable", "topN": 40, "maxErrorRate": 40, "timeRange": "7d"},
    )
    if status in (401, 403):
        return False, [], f"authentication failed HTTP {status}"
    if status >= 400:
        return False, [], f"catalog failed HTTP {status}"
    ids = [str(x).strip() for x in (payload.get("ids") or []) if str(x).strip()]
    return True, ids, f"catalog ok count={len(ids)}"


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


def _gemini_models(token: str | None) -> tuple[bool, dict[str, dict], str]:
    if not token:
        return False, {}, "missing credential"
    status, payload = _get_json("https://generativelanguage.googleapis.com/v1beta/models", token=token, query={"key": token})
    if status in (400, 401, 403):
        return False, {}, f"authentication failed HTTP {status}"
    if status >= 400:
        return False, {}, f"model catalog failed HTTP {status}"
    rows = payload.get("models") or []
    catalog: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("baseModelId") or row.get("name", "").replace("models/", ""))
        actions = {str(x) for x in (row.get("supportedGenerationMethods") or [])}
        if model_id and "generateContent" in actions:
            catalog[model_id] = row
    return True, catalog, "catalog ok"


def _is_zero_price(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    try:
        return float(pricing.get("prompt", pricing.get("input", "-1"))) == 0 and float(pricing.get("completion", pricing.get("output", "-1"))) == 0
    except (TypeError, ValueError):
        return False


def _supports_response_format(model: dict) -> bool:
    supported = model.get("supported_parameters") or []
    return "response_format" in {str(x).strip() for x in supported}


def _fallback_quality(model_id: str) -> tuple[float, float, str]:
    """Conservative priors for trusted models when benchmark evidence is absent."""
    overrides = {
        "nvidia/nemotron-3-ultra-550b-a55b:free": (98, 94, "curated-independent"),
        "nvidia/nemotron-3-super-120b-a12b:free": (97, 94, "curated-independent"),
        "openai/gpt-oss-120b:free": (94, 97, "curated-independent"),
        "openai/gpt-oss-120b": (95, 99, "curated-independent"),
        "qwen/qwen3.6-27b": (93, 97, "curated-independent"),
        "openai/gpt-oss-20b": (84, 91, "curated-independent"),
        "openai/gpt-oss-20b:free": (84, 91, "curated-independent"),
        "minimax-m3-free": (89, 95, "curated-independent"),
    }
    return overrides.get(model_id.lower(), (0, 0, "unverified"))


def _apply_evidence(model: dict, benchmark: dict | None, task_usage: dict[str, float], generated_at: str) -> None:
    from free_model_evidence import benchmark_score, quality_score

    model_id = str(model.get("id", ""))
    normalized = model_id.lower().removesuffix(":free")
    if benchmark:
        model.update(benchmark)
        model["quality_evidence"] = "openrouter-artificial-analysis"
        model["base_quality"] = benchmark_score(benchmark)
        model["task_fit"] = round(0.85 * benchmark_score(benchmark) + 0.15 * min(100.0, task_usage.get(normalized, 0.0) * 10.0), 3)
    elif not model.get("base_quality"):
        base, fit, evidence = _fallback_quality(model_id)
        model["base_quality"] = base
        model["task_fit"] = fit
        model["quality_evidence"] = evidence
    model["quality_score"] = quality_score(model, generated_at=generated_at)


def refresh() -> dict:
    static = _load_static()
    registry = copy.deepcopy(static["registry"])
    token_or = os.getenv("OPENROUTER_API_KEY")
    token_groq = os.getenv("GROQ_API_KEY")
    token_kira = os.getenv("KIRAAI_API_KEY")
    token_gemini = os.getenv("GEMINI_API_KEY")
    token_flr = os.getenv("FREE_LLM_ROUTER_API_KEY")
    generated_at = datetime.now(timezone.utc).isoformat()

    or_auth_ok, or_auth_reason = _openrouter_auth(token_or)
    or_models, or_catalog_reason = _openrouter_models(token_or)
    or_benchmarks, or_benchmark_reason = _openrouter_benchmarks(token_or)
    or_task_usage = _openrouter_task_evidence(token_or)
    groq_ok, groq_models, groq_reason = _groq_models(token_groq)
    kira_ok, kira_models, kira_reason = _kira_models(token_kira)
    gemini_ok, gemini_models, gemini_reason = _gemini_models(token_gemini)
    flr_ok, flr_ids, flr_reason = _free_llm_router_ids(token_flr)
    discovery: list[dict] = []

    for provider in registry.get("providers", []) or []:
        family = str(provider.get("family", "")).strip().lower()
        if family == "openrouter":
            provider["credential_valid"] = or_auth_ok
            provider["validation"] = f"{or_auth_reason}; {or_catalog_reason}; {or_benchmark_reason}"
            catalog = or_models
        elif family == "groq":
            provider["credential_valid"] = groq_ok
            provider["validation"] = groq_reason
            catalog = groq_models
        elif family == "kiraai":
            provider["credential_valid"] = kira_ok
            provider["validation"] = kira_reason
            catalog = kira_models
        elif family == "gemini":
            provider["credential_valid"] = gemini_ok
            provider["validation"] = gemini_reason
            catalog = gemini_models
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
                if not live or not provider["credential_valid"]:
                    model["enabled"] = False
                    model["runtime_reason"] = "provider_unavailable"
                else:
                    model["free"] = _is_zero_price(live)
                    model["context_length"] = int(live.get("context_length") or 0)
                    model["response_format"] = _supports_response_format(live) or bool(model.get("response_format"))
                    if not model["free"]:
                        model["enabled"] = False
                        model["runtime_reason"] = "not_free"
            elif family == "groq" and not live:
                model["enabled"] = False
                model["runtime_reason"] = "not_listed"
            elif family == "kiraai":
                if not live or not provider["credential_valid"]:
                    model["enabled"] = False
                    model["runtime_reason"] = "provider_unavailable"
                else:
                    model["free"] = bool(model.get("free") is True)
                    model["context_length"] = int(live.get("context_length") or 0)
                    model["response_format"] = _supports_response_format(live) or bool(model.get("response_format"))
                    if not model["free"]:
                        model["enabled"] = False
                        model["runtime_reason"] = "not_free"
            elif family == "gemini":
                if not live or not provider["credential_valid"]:
                    model["enabled"] = False
                    model["runtime_reason"] = "provider_unavailable"
                else:
                    model["context_length"] = int(live.get("inputTokenLimit") or 0)
                    model["response_format"] = True
                    model["free"] = True

            if model.get("enabled"):
                _apply_evidence(model, or_benchmarks.get(model_id.lower().removesuffix(":free")), or_task_usage, generated_at)

    trusted_ids = {str(m.get("id")) for p in registry.get("providers", []) for m in p.get("models", [])}
    if or_auth_ok:
        for model_id, live in sorted(or_models.items()):
            if model_id in trusted_ids or not _is_zero_price(live):
                continue
            benchmark = or_benchmarks.get(model_id.lower().removesuffix(":free"))
            if not benchmark:
                continue
            row = {
                "id": model_id,
                "family": "openrouter",
                "free": True,
                "chat_capable": "text" in (live.get("architecture", {}).get("input_modalities") or ["text"]),
                "json_capable": True,
                "response_format": _supports_response_format(live),
                "context_length": int(live.get("context_length") or 0),
                "priority": 1000,
                "reliability_score": 80,
                "promotion_status": "dynamic-benchmark-qualified",
            }
            _apply_evidence(row, benchmark, or_task_usage, generated_at)
            if row["quality_score"] >= 45:
                discovery.append(row)

    if flr_ok and or_auth_ok:
        discovery_ids = {str(x.get("id")) for x in discovery}
        for model_id in flr_ids:
            live = or_models.get(model_id)
            if not live or not _is_zero_price(live) or model_id in trusted_ids or model_id in discovery_ids:
                continue
            benchmark = or_benchmarks.get(model_id.lower().removesuffix(":free"))
            row = {
                "id": model_id,
                "family": "openrouter",
                "free": True,
                "chat_capable": "text" in (live.get("architecture", {}).get("input_modalities") or ["text"]),
                "json_capable": True,
                "response_format": _supports_response_format(live),
                "context_length": int(live.get("context_length") or 0),
                "priority": 950,
                "reliability_score": 85,
                "promotion_status": "free-llm-router-qualified",
                "discovery_source": "free-llm-router",
            }
            _apply_evidence(row, benchmark, or_task_usage, generated_at)
            if row["quality_score"] >= 45:
                discovery.append(row)

    discovery.sort(key=lambda x: (-float(x.get("quality_score", 0)), x["id"]))
    runtime = {
        "runtime": {
            "schema_version": 5,
            "generated_at": generated_at,
            "discovery_candidates": discovery[:40],
            "provider_validation": {
                "openrouter": {"valid": or_auth_ok, "reason": f"{or_auth_reason}; {or_catalog_reason}; {or_benchmark_reason}"},
                "groq": {"valid": groq_ok, "reason": groq_reason},
                "kiraai": {"valid": kira_ok, "reason": kira_reason},
                "gemini": {"valid": gemini_ok, "reason": gemini_reason},
                "free_llm_router": {"valid": flr_ok, "reason": flr_reason},
            },
            "evidence": {
                "benchmark_source": "OpenRouter API -> Artificial Analysis",
                "task_source": "OpenRouter 7d task classifications",
                "benchmark_count": len(or_benchmarks),
                "task_model_count": len(or_task_usage),
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
    if args.strict and not any(validation[name]["valid"] for name in ("groq", "openrouter", "kiraai", "gemini")):
        raise SystemExit("No core production provider credential validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
