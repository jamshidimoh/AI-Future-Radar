"""Dynamic, quality-first production ordering for free LLMs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import requests
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
    return provider.get("credential_valid") is not False


def _quality_score(model: dict) -> float:
    try:
        base = float(model.get("quality_score", model.get("base_quality", 0)) or 0)
        fit = float(model.get("task_fit", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(base * 0.80 + fit * 0.20, 3)


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
            if int(model.get("priority", 9999)) >= 1000 or not model.get("id"):
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
            row["quality_score"] = _quality_score(row)
            rows.append(row)

    # Runtime discovery can promote only candidates that already carry explicit
    # quality evidence. Unknown models remain quarantined instead of guessing.
    known_ids = {row["id"] for row in rows}
    for candidate in discovered_candidates():
        if not isinstance(candidate, dict) or candidate.get("id") in known_ids:
            continue
        if candidate.get("free") is not True or candidate.get("chat_capable") is not True:
            continue
        score = _quality_score(candidate)
        if score < 88:
            continue
        family = str(candidate.get("family", "")).strip().lower()
        env_name = {"openrouter": "OPENROUTER_API_KEY", "kiraai": "KIRAAI_API_KEY", "groq": "GROQ_API_KEY"}.get(family)
        if not _credential_available(env_name):
            continue
        row = dict(candidate)
        row["credential_env"] = env_name
        row["quality_score"] = score
        row["priority"] = int(row.get("priority", 1000))
        rows.append(row)

    rows.sort(key=lambda x: (-float(x["quality_score"]), int(x.get("priority", 9999)), x["id"]))
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


def _kiraai_call(router, system_prompt, user_content, model):
    key = __import__("os").getenv("KIRAAI_API_KEY")
    if not key:
        return None
    payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], "max_tokens": 850, "temperature": 0.15}
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


def build_production_chain(router):
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
        elif family == "kiraai":
            fn = lambda sp, uc, m=model_id: _kiraai_call(router, sp, uc, m)
        else:
            continue
        display_family = {"openrouter": "OpenRouter", "kiraai": "KiraAI", "groq": "Groq"}.get(family, family.title())
        chain.append((f"{display_family}:{model_id}", fn))
        if len(chain) >= max_runtime_candidates:
            break

    import os
    if os.getenv("RADAR_ENABLE_GEMINI_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and _credential_available("GEMINI_API_KEY"):
        chain.append(("Gemini", router._gemini))
    if os.getenv("RADAR_ENABLE_HF_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and _credential_available("HF_TOKEN"):
        chain.append(("HuggingFace", router._huggingface))
    if not chain:
        raise RuntimeError("No credentialed trusted production LLM model is available")
    return chain
