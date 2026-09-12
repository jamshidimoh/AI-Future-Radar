"""Dynamic, evidence-backed production ordering for free LLM deployments."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "free_model_registry.yaml"
RUNTIME_REGISTRY_PATH = ROOT / "artifacts" / "free_model_registry.runtime.yaml"

_PROVIDER_ORDER = {"groq": 0, "nararouter": 1, "openrouter": 2, "kiraai": 3, "gemini": 4, "huggingface": 5}
_BLOCKED_OPENROUTER_IDS = {"openrouter/free", "openrouter/auto"}
NARA_DEFAULT_MODEL = "auto/bynara"


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
    source = env if env is not None else os.environ
    return bool(env_name and source.get(str(env_name).strip()))


def _provider_runtime_available(provider: dict) -> bool:
    return provider.get("credential_valid") is not False


def _blocked_model_id(family: str, model_id: str) -> bool:
    if family != "openrouter":
        return False
    return model_id.strip().casefold() in _BLOCKED_OPENROUTER_IDS


def _quality_score(model: dict) -> float:
    try:
        explicit = model.get("quality_score")
        if explicit is not None:
            return round(float(explicit), 3)
        base = float(model.get("base_quality", 0) or 0)
        fit = float(model.get("task_fit", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(base * 0.80 + fit * 0.20, 3)


def _routing_key(entry: dict) -> tuple:
    family = str(entry.get("family") or "").strip().casefold()
    return (
        _PROVIDER_ORDER.get(family, 99),
        -_quality_score(entry),
        int(entry.get("priority", 9999) or 9999),
        str(entry.get("id", "")),
    )


def discovered_candidates() -> list[dict]:
    data = _load().get("runtime", {})
    rows = data.get("discovery_candidates", []) if isinstance(data, dict) else []
    return list(rows) if isinstance(rows, list) else []


def canonical_entries() -> list[dict]:
    data = _load().get("registry", {})
    rows: list[dict] = []
    for provider in data.get("providers", []) or []:
        family = str(provider.get("family", "")).strip().lower()
        credential_env = provider.get("credential_env")
        if not _credential_available(credential_env) or not _provider_runtime_available(provider):
            continue
        for model in provider.get("models", []) or []:
            if not isinstance(model, dict) or model.get("enabled", True) is False:
                continue
            model_id = str(model.get("id") or "").strip()
            if not model_id or _blocked_model_id(family, model_id):
                continue
            if int(model.get("priority", 9999)) >= 1000:
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
            row["deployment_id"] = f"{family}:{row['id']}"
            row["quality_score"] = _quality_score(row)
            if row["quality_score"] <= 0:
                continue
            rows.append(row)

    known_ids = {row["id"] for row in rows}
    for candidate in discovered_candidates():
        if not isinstance(candidate, dict):
            continue
        model_id = str(candidate.get("id") or "").strip()
        family = str(candidate.get("family") or "").strip().casefold()
        if not model_id or model_id in known_ids or _blocked_model_id(family, model_id):
            continue
        if candidate.get("free") is not True or candidate.get("chat_capable") is not True:
            continue
        if data.get("require_json_capability", True) and candidate.get("json_capable") is not True:
            continue
        score = _quality_score(candidate)
        if score < 50:
            continue
        env_name = {
            "openrouter": "OPENROUTER_API_KEY",
            "kiraai": "KIRAAI_API_KEY",
            "groq": "GROQ_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "huggingface": "HF_TOKEN",
        }.get(family)
        if not _credential_available(env_name):
            continue
        row = dict(candidate)
        row["credential_env"] = env_name
        row["deployment_id"] = f"{family}:{row['id']}"
        row["quality_score"] = score
        row["priority"] = int(row.get("priority", 1000))
        rows.append(row)

    return sorted(rows, key=_routing_key)


def ranked_entries() -> list[dict]:
    """Return currently usable deployments using provider-first reliability order."""
    from free_model_service import get_intelligence
    ranked = get_intelligence().rank(canonical_entries())
    return sorted(ranked, key=_routing_key)


def model_capability(model_id: str) -> dict:
    for entry in canonical_entries():
        if entry.get("id") == model_id:
            return entry
    for entry in discovered_candidates():
        if entry.get("id") == model_id:
            return entry
    return {}


def _kiraai_call(router, system_prompt, user_content, model):
    key = os.getenv("KIRAAI_API_KEY")
    if not key:
        return None
    payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], "max_tokens": 700, "temperature": 0.15}
    if model_capability(model).get("response_format"):
        payload["response_format"] = {"type": "json_object"}
    response = requests.post("https://kiraai.vn/api/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=10)
    if response.status_code in (401, 402, 403, 404, 429):
        raise router.QuotaExceeded(f"KiraAI {model}: HTTP {response.status_code} {response.text[:500]}")
    response.raise_for_status()
    choices = response.json().get("choices") or []
    if not choices:
        raise ValueError("KiraAI response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    if content is None:
        raise ValueError("KiraAI response content not found")
    return content


def _litellm_model_name(entry: dict) -> str:
    family = str(entry["family"]).lower()
    model_id = str(entry["id"])
    if family == "openrouter":
        return f"openrouter/{model_id}"
    if family == "groq":
        return f"groq/{model_id}"
    if family == "kiraai":
        return f"openai/{model_id}"
    if family == "gemini":
        return f"gemini/{model_id}"
    raise ValueError(f"Unsupported LiteLLM provider family: {family}")


def build_litellm_model_list() -> list[dict]:
    """Translate ranked registry plus the independent Nara free lane into deployments."""
    rows: list[dict] = []
    ranked = ranked_entries()
    order = 1
    for entry in ranked:
        env_name = str(entry.get("credential_env") or "").strip()
        api_key = os.getenv(env_name, "").strip()
        if not api_key:
            continue
        params = {"model": _litellm_model_name(entry), "api_key": api_key, "timeout": 8, "order": 1}
        if entry.get("family") == "kiraai":
            params["api_base"] = "https://kiraai.vn/api/v1"
        rows.append({
            "model_name": f"radar-production-{order}",
            "litellm_params": params,
            "model_info": {
                "id": entry["deployment_id"],
                "quality_score": entry["quality_score"],
                "provider_family": entry["family"],
                "rank": order,
                "response_format": bool(entry.get("response_format")),
            },
        })
        order += 1
        if entry.get("family") == "groq" and os.getenv("NARAROUTER_API_KEY", "").strip():
            rows.append({
                "model_name": f"radar-production-{order}",
                "litellm_params": {"model": f"openai/{os.getenv('NARA_MODEL', NARA_DEFAULT_MODEL).strip()}", "api_key": os.getenv("NARAROUTER_API_KEY", "").strip(), "api_base": "https://router.bynara.id/v1", "timeout": 8, "order": 1},
                "model_info": {
                    "id": f"nararouter:{os.getenv('NARA_MODEL', NARA_DEFAULT_MODEL).strip()}",
                    "quality_score": 62.0,
                    "provider_family": "nararouter",
                    "rank": order,
                    "response_format": False,
                },
            })
            order += 1
    return rows


def build_production_chain(router):
    chain: list[tuple[str, object]] = []
    max_runtime_candidates = int(_load().get("registry", {}).get("max_runtime_candidates", 18) or 18)
    inserted_nara = False
    for entry in ranked_entries()[:max_runtime_candidates]:
        family = entry["family"]
        model_id = entry["id"]
        if family == "groq":
            fn = lambda sp, uc, m=model_id: router._groq(sp, uc, m)
        elif family == "openrouter":
            fn = lambda sp, uc, m=model_id: router._openrouter(sp, uc, m)
        elif family == "kiraai":
            fn = lambda sp, uc, m=model_id: _kiraai_call(router, sp, uc, m)
        else:
            continue
        display_family = {"openrouter": "OpenRouter", "kiraai": "KiraAI", "groq": "Groq"}.get(family, family.title())
        chain.append((f"{display_family}:{model_id}", fn))
        if family == "groq" and not inserted_nara and os.getenv("NARAROUTER_API_KEY", "").strip():
            nara_model = os.getenv("NARA_MODEL", NARA_DEFAULT_MODEL).strip()
            chain.append((f"NaraRouter:{nara_model}", lambda sp, uc, m=nara_model: router._nara(sp, uc, m)))
            inserted_nara = True

    if os.getenv("RADAR_ENABLE_GEMINI_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and _credential_available("GEMINI_API_KEY"):
        chain.append(("Gemini", router._gemini))
    if os.getenv("RADAR_ENABLE_HF_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and _credential_available("HF_TOKEN"):
        chain.append(("HuggingFace", router._huggingface))
    if not chain:
        raise RuntimeError("No credentialed trusted production LLM model is available")
    return chain
