"""Production-only LLM routing policy with bounded, quota-aware failover."""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import requests

import src.llm_router_light as router
from src.free_model_registry import build_production_chain
from src.state_io import load_json_state

logger = logging.getLogger(__name__)

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


def _rate_limit_retry_delay(message: str, *, max_seconds: float = 8.0) -> float:
    """Extract a provider-supplied short retry delay, capped for production budget."""
    text = str(message or "")
    match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s)", text, re.IGNORECASE)
    if not match:
        return 0.0
    value = float(match.group(1))
    delay = value / 1000.0 if match.group(2).lower() == "ms" else value
    return max(0.0, min(delay, max_seconds))


def _load_health() -> dict:
    value = load_json_state(HEALTH_PATH, {}, label="LLM health state")
    return value if isinstance(value, dict) else {}


def _persistently_unavailable(deployment_id: str, *, recovery_probe: bool = False) -> bool:
    """Skip persisted health cooldowns, except for bounded half-open recovery probes."""
    if os.getenv("RADAR_PRODUCTION_MODE", "0").strip().lower() not in {"1", "true", "yes"}:
        return False
    health = _load_health()
    now = time.time()
    models = health.get("models") or {}
    providers = health.get("providers") or {}

    def _find(section, target):
        if not isinstance(section, dict):
            return None
        target = str(target or "").strip().casefold()
        return next(
            (row for key, row in section.items() if str(key).strip().casefold() == target and isinstance(row, dict)),
            None,
        )

    model = _find(models, deployment_id)
    family = router._provider_family(deployment_id)
    provider = _find(providers, family)
    model_disabled = isinstance(model, dict) and float(model.get("disabled_until", 0) or 0) > now
    provider_disabled = isinstance(provider, dict) and float(provider.get("disabled_until", 0) or 0) > now
    if not (model_disabled or provider_disabled):
        return False
    if not recovery_probe:
        return True

    recoverable = {"quota", "rate_limit", "transient"}
    blocked = {"auth", "model", "wallet"}
    model_reason = str((model or {}).get("last_error") or "").strip().casefold()
    provider_reason = str((provider or {}).get("last_error") or "").strip().casefold()
    has_recoverable = model_reason in recoverable or provider_reason in recoverable
    has_blocked = model_reason in blocked or provider_reason in blocked
    if has_recoverable and not has_blocked:
        print(
            f"[Production Circuit] half_open_probe={deployment_id} reason=persisted_recoverable_health",
            flush=True,
        )
        return False
    return True

def _omniroute_call(system_prompt, user_content):
    """Try OmniRoute first when an operator exposes a live gateway endpoint.

    OmniRoute is deliberately an optional primary router: if the endpoint is not
    configured or fails, the existing registry/circuit-breaker chain remains the
    authoritative fallback. The radar therefore never becomes dependent on a
    single routing gateway.
    """
    base_url = os.getenv("OMNIROUTE_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        return None, None
    api_key = os.getenv("OMNIROUTE_API_KEY", "").strip()
    model = os.getenv("OMNIROUTE_MODEL", "auto/smart").strip() or "auto/smart"
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.15,
        "max_tokens": max(256, int(os.getenv("RADAR_LLM_MAX_TOKENS", "700") or 700)),
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    timeout = max(0.5, min(8.0, float(os.getenv("OMNIROUTE_TIMEOUT_SECONDS", "8") or 8)))
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"OmniRoute HTTP {response.status_code}: {response.text[:500]}")
        data = response.json()
        choices = data.get("choices") or []
        content = None
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
        if not content:
            raise RuntimeError("OmniRoute response has no content")
        decision = response.headers.get("X-OmniRoute-Decision", "")
        selected = str(data.get("model") or decision or model)
        print(
            f"[OmniRoute Primary] success=true requested={model} selected={selected} "
            f"decision={decision[:300]}",
            flush=True,
        )
        return content, f"OmniRoute:{selected}"
    except Exception as exc:
        print(
            f"[OmniRoute Primary] success=false reason={type(exc).__name__}: {exc}; falling back to production chain",
            flush=True,
        )
        logger.warning("OmniRoute primary routing failed: %s", exc, exc_info=True)
        return None, None


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
            # A deployment may become the only remaining option after earlier
            # providers fail during this same request. In that case, allow a bounded
            # half-open probe for persisted recoverable health even if the registry
            # was built while another deployment was still healthy.
            recovery_probe = bool(deployment.get("model_info", {}).get("health_recovery_probe"))
            if not recovery_probe and attempts > 0:
                recovery_probe = True
            if _persistently_unavailable(deployment_id, recovery_probe=recovery_probe):
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
                retry_delay = _rate_limit_retry_delay(message)
                if reason == "quota" and not (_is_provider_quota(message) or _is_provider_auth(message)) and retry_delay > 0 and attempts < max_attempts:
                    retry_budget = deadline - time.monotonic()
                    if retry_budget > retry_delay + 0.25:
                        print(f"[Production Circuit] rate_limit_retry={deployment_id} delay={retry_delay:.2f}s", flush=True)
                        time.sleep(retry_delay)
                        attempts += 1
                        try:
                            response = router._call_direct_deployment(
                                litellm_router,
                                deployment,
                                system_prompt,
                                user_content,
                                max_tokens=max_tokens,
                                timeout=max(0.5, min(8.0, deadline - time.monotonic())),
                            )
                            content = getattr(response.choices[0].message, "content", None) if getattr(response, "choices", None) else None
                            if not content:
                                raise ValueError("LLM response has no content")
                            selected = str(getattr(response, "model", deployment_id))
                            print(f"[Production Circuit] success_after_retry={deployment_id} model={selected} attempts={attempts}", flush=True)
                            return content, deployment_id
                        except Exception as retry_exc:
                            last_error = retry_exc
                            message = str(retry_exc)
                            reason = router._failure_class(message)
                logger.warning(
                    "Production provider attempt failed provider=%s model=%s exception=%s: %s",
                    family,
                    deployment_id,
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
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
                print(
                    f"[Production Circuit] failed={deployment_id} reason={reason} scope={scope}: "
                    f"exception={type(exc).__name__} provider={family} model={deployment_id} {message}",
                    flush=True,
                )
                return None

        # OmniRoute is the first model-selection layer when configured. It owns
        # dynamic provider/model choice (auto/smart by default) and its own
        # health/quota/fallback logic. The local registry remains the hard fallback.
        if os.getenv("OMNIROUTE_BASE_URL", "").strip():
            omni_result = _omniroute_call(system_prompt, user_content)
            if omni_result[0]:
                return omni_result

        for deployment in model_list:
            result = _try_deployment(deployment)
            if result:
                return result
            if attempts >= max_attempts:
                break

        emergency_fallbacks = []
        if os.getenv("RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK", "0").strip().lower() in {"1", "true", "yes"}:
            emergency_fallbacks.append(("LocalOllamaFree", router._ollama_local))
        if os.getenv("RADAR_ENABLE_GEMINI_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and os.getenv("GEMINI_API_KEY"):
            emergency_fallbacks.append(("Gemini", router._gemini))
        if os.getenv("RADAR_ENABLE_OPENROUTER_FREE_ROUTER", "0").strip().lower() in {"1", "true", "yes"} and os.getenv("OPENROUTER_API_KEY"):
            emergency_fallbacks.append(("OpenRouterFreeRouter", router._openrouter_free_router))
        if os.getenv("RADAR_ENABLE_HF_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and os.getenv("HF_TOKEN"):
            emergency_fallbacks.append(("HuggingFace", router._huggingface))

        for emergency_name, emergency_fn in emergency_fallbacks:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                print(f"[Production Circuit] {emergency_name.lower()}_emergency_attempt=1", flush=True)
                future = router._CALL_EXECUTOR.submit(emergency_fn, system_prompt, user_content)
                emergency_limit = 18.0 if emergency_name == "LocalOllamaFree" else 6.0
                content = future.result(timeout=max(0.5, min(emergency_limit, remaining)))
                if content:
                    print(f"[Production Circuit] success={emergency_name} emergency=1", flush=True)
                    return content, emergency_name
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Production provider attempt failed provider=%s model=%s exception=%s: %s",
                    emergency_name.lower(),
                    emergency_name,
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
                print(
                    f"[Production Circuit] failed={emergency_name} reason={router._failure_class(str(exc))} "
                    f"scope=emergency: exception={type(exc).__name__} provider={emergency_name.lower()} model={emergency_name} {exc}",
                    flush=True,
                )

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
