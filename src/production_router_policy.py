"""Production-only LLM routing policy with bounded, quota-aware failover."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import llm_router_light as router
except ImportError:  # pragma: no cover
    src_dir = str(Path(__file__).resolve().parent)
    if str(src_dir) not in sys.path:
        sys.path.insert(0, src_dir)
    import llm_router_light as router

try:
    from .free_model_registry import build_production_chain
except ImportError:  # pragma: no cover
    from free_model_registry import build_production_chain

ROOT = Path(__file__).resolve().parents[1]
HEALTH_PATH = ROOT / "data" / "llm_health.json"
_PROVIDER_QUOTA_PATTERNS = re.compile(r"(?:free-models-per-day|x-ratelimit-(?:remaining|reset).*?(?:0|quota)|account[_ -]?limit|daily[_ -]?quota|quota.*(?:exhaust|deplet)|(?:requests?|tokens?)/(?:day|daily)|provider.*(?:quota|limit)|insufficient.*(?:credit|balance))", re.IGNORECASE)
_PROVIDER_AUTH_PATTERNS = re.compile(r"(?:\b401\b|unauthorized|invalid.*(?:api|credential|key|token)|authentication.*(?:failed|error))", re.IGNORECASE)
_KIRAAI_WALLET_PATTERN = re.compile(r"(?:insufficient.*(?:vnd|wallet|balance)|wallet.*balance|vnd.*balance)", re.IGNORECASE)


def _is_provider_quota(message: str) -> bool:
    text = str(message or "")
    if re.search(r"upstream_provider_shared_pool", text, re.IGNORECASE):
        return False
    if re.search(r"\b402\b", text):
        return True
    return bool(_PROVIDER_QUOTA_PATTERNS.search(text))


def _is_provider_auth(message: str) -> bool:
    return bool(_PROVIDER_AUTH_PATTERNS.search(str(message or "")))


def _is_kira_wallet_only(message: str, family: str) -> bool:
    return family == "kiraai" and bool(_KIRAAI_WALLET_PATTERN.search(str(message or "")))


def _load_health() -> dict:
    try:
        value = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _persistently_unavailable(deployment_id: str) -> bool:
    """Skip providers/models whose persisted health cooldown is still active in production."""
    if os.getenv("RADAR_PRODUCTION_MODE", "0").strip().lower() not in {"1", "true", "yes"}:
        return False
    health = _load_health()
    now = time.time()
    models = health.get("models") or {}
    providers = health.get("providers") or {}
    model = models.get(deployment_id) if isinstance(models, dict) else None
    if isinstance(model, dict) and float(model.get("disabled_until", 0) or 0) > now:
        return True
    family = router._provider_family(deployment_id)
    provider = providers.get(family) if isinstance(providers, dict) else None
    if isinstance(provider, dict) and float(provider.get("disabled_until", 0) or 0) > now:
        return True
    return False


def _install_production_circuit_breaker() -> None:
    if getattr(router, "_PRODUCTION_CIRCUIT_BREAKER_INSTALLED", False):
        return

    max_attempts = max(1, int(os.getenv("RADAR_MAX_LLM_ATTEMPTS", "8") or 8))
    budget_seconds = max(5.0, float(os.getenv("RADAR_ROUTER_BUDGET_SECONDS", "24") or 24))
    max_tokens = max(256, int(os.getenv("RADAR_LLM_MAX_TOKENS", "700") or 700))

    def _call_litellm_guarded(system_prompt, user_content):
        litellm_router = router._get_litellm_router()
        model_list = router._litellm_model_list() if litellm_router is not None else []
        deadline = time.monotonic() + budget_seconds
        last_error = None
        attempts = 0
        skipped_families: set[str] = set()
        tried: set[str] = set()

        def _try_deployment(deployment):
            nonlocal attempts, last_error
            deployment_id = deployment["model_info"]["id"]
            family = router._provider_family(deployment_id)
            if deployment_id in tried:
                return None
            tried.add(deployment_id)
            if _persistently_unavailable(deployment_id):
                print(f"[Production Circuit] skipped={deployment_id} reason=persisted_health", flush=True)
                return None
            if family in skipped_families or family in router._DISABLED_FAMILIES:
                print(f"[Production Circuit] skipped={deployment_id} reason=provider_disabled", flush=True)
                return None
            if router._model_is_disabled(deployment_id):
                print(f"[Production Circuit] skipped={deployment_id} reason=model_cooldown", flush=True)
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print("[Production Circuit] budget_exhausted=1", flush=True)
                return None
            if attempts >= max_attempts:
                print(f"[Production Circuit] attempt_budget_exhausted={max_attempts}", flush=True)
                return None
            attempts += 1
            try:
                response = router._call_direct_deployment(litellm_router, deployment, system_prompt, user_content, max_tokens=max_tokens, timeout=max(0.5, min(8.0, remaining)))
                content = getattr(response.choices[0].message, "content", None) if getattr(response, "choices", None) else None
                if not content:
                    raise ValueError("LLM response has no content")
                selected = str(getattr(response, "model", deployment_id))
                print(f"[Production Circuit] success={deployment_id} model={selected} attempts={attempts}", flush=True)
                return content, deployment_id
            except Exception as exc:
                last_error = exc
                message = str(exc)
                reason = router._failure_class(message)
                if _is_kira_wallet_only(message, family):
                    skipped_families.add(family)
                    with router._STATE_LOCK:
                        router._DISABLED_FAMILIES.add(family)
                        router._DISABLED.add(deployment_id)
                    router._disable(deployment_id, "quota")
                    scope = "provider"
                elif _is_provider_quota(message) or _is_provider_auth(message):
                    skipped_families.add(family)
                    with router._STATE_LOCK:
                        router._DISABLED_FAMILIES.add(family)
                        router._DISABLED.add(deployment_id)
                    scope = "provider"
                else:
                    router._disable(deployment_id, reason)
                    scope = "model"
                print(f"[Production Circuit] failed={deployment_id} reason={reason} scope={scope}: {message}", flush=True)
                return None

        for deployment in model_list:
            result = _try_deployment(deployment)
            if result:
                return result
            if attempts >= max_attempts:
                break

        if os.getenv("RADAR_ENABLE_HF_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and os.getenv("HF_TOKEN"):
            remaining = deadline - time.monotonic()
            if remaining > 0:
                try:
                    print("[Production Circuit] hf_emergency_attempt=1", flush=True)
                    future = router._CALL_EXECUTOR.submit(router._huggingface, system_prompt, user_content)
                    content = future.result(timeout=max(0.5, min(6.0, remaining)))
                    if content:
                        print("[Production Circuit] success=HuggingFace emergency=1", flush=True)
                        return content, "HuggingFace"
                except Exception as exc:
                    last_error = exc
                    print(f"[Production Circuit] failed=HuggingFace reason={router._failure_class(str(exc))} scope=model: {exc}", flush=True)

        if last_error is not None:
            print(f"[Production Circuit] exhausted={type(last_error).__name__}: {last_error}", flush=True)
        return None, None

    router._call_litellm = _call_litellm_guarded
    router._PRODUCTION_CIRCUIT_BREAKER_INSTALLED = True
    print(f"[Production Circuit] installed max_attempts={max_attempts} budget_seconds={budget_seconds:.1f} max_tokens={max_tokens}", flush=True)


def apply() -> None:
    if getattr(router, "_PRODUCTION_POLICY_APPLIED", False):
        return
    chain = build_production_chain(router)
    if not chain:
        raise RuntimeError("Production model registry produced an empty provider chain")
    router._CHAIN_CACHE = list(chain)
    router._PRODUCTION_POLICY_APPLIED = True
    _install_production_circuit_breaker()
    print("[Production Model Registry] chain=" + ", ".join(name for name, _ in chain), flush=True)
