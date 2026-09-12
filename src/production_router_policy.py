"""Production-only LLM routing policy.

Production uses the trusted free-model registry for deterministic quality-first
ordering. Provider/account failures trip a family circuit, while model and
upstream-shared-pool failures remain model-scoped. Hugging Face is reserved for
an explicit last-resort emergency lane because its free allowance is limited.
"""
from __future__ import annotations

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

_PROVIDER_QUOTA_PATTERNS = re.compile(
    r"(?:"
    r"free-models-per-day|"
    r"x-ratelimit-(?:remaining|reset).*?(?:0|quota)|"
    r"account[_ -]?limit|"
    r"daily[_ -]?quota|"
    r"quota.*(?:exhaust|deplet)|"
    r"(?:requests?|tokens?)/(?:day|daily)|"
    r"provider.*(?:quota|limit)|"
    r"insufficient.*(?:credit|balance)"
    r")",
    re.IGNORECASE,
)
_KIRAAI_WALLET_PATTERN = re.compile(r"(?:insufficient.*(?:vnd|wallet|balance)|wallet.*balance|vnd.*balance)", re.IGNORECASE)


def _is_provider_quota(message: str) -> bool:
    """Return True only for evidence that the provider/account is exhausted."""
    text = str(message or "")
    if re.search(r"upstream_provider_shared_pool", text, re.IGNORECASE):
        return False
    if re.search(r"\b402\b", text):
        return True
    return bool(_PROVIDER_QUOTA_PATTERNS.search(text))


def _is_kira_wallet_only(message: str, family: str) -> bool:
    return family == "kiraai" and bool(_KIRAAI_WALLET_PATTERN.search(str(message or "")))


def _install_production_circuit_breaker() -> None:
    """Replace the production LiteLLM loop with quota-aware bounded failover."""
    if getattr(router, "_PRODUCTION_CIRCUIT_BREAKER_INSTALLED", False):
        return

    # Four attempts were too small for the real production chain: transient
    # failures in the first OpenRouter/Groq deployments could consume the whole
    # budget before KiraAI was ever reached. Eight preserves a hard bound while
    # allowing cross-provider failover to reach the configured KiraAI lane.
    max_attempts = max(1, int(os.getenv("RADAR_MAX_LLM_ATTEMPTS", "8") or 8))
    budget_seconds = max(5.0, float(os.getenv("RADAR_ROUTER_BUDGET_SECONDS", "24") or 24))

    def _call_litellm_guarded(system_prompt, user_content):
        litellm_router = router._get_litellm_router()
        model_list = router._litellm_model_list() if litellm_router is not None else []
        deadline = time.monotonic() + budget_seconds
        last_error = None
        attempts = 0
        skipped_families: set[str] = set()

        def _try_deployment(deployment):
            nonlocal attempts, last_error
            deployment_id = deployment["model_info"]["id"]
            family = router._provider_family(deployment_id)
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
                response = litellm_router.completion(
                    model=deployment["model_name"],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    timeout=max(0.5, min(8.0, remaining)),
                )
                content = getattr(response.choices[0].message, "content", None) if getattr(response, "choices", None) else None
                if not content:
                    raise ValueError("LiteLLM response has no content")
                selected = str(getattr(response, "model", deployment_id))
                print(f"[Production Circuit] success={deployment_id} model={selected} attempts={attempts}", flush=True)
                return content, deployment_id
            except Exception as exc:
                last_error = exc
                message = str(exc)
                reason = router._failure_class(message)
                if _is_kira_wallet_only(message, family):
                    router._disable(deployment_id, "quota")
                    scope = "model"
                elif _is_provider_quota(message) or reason == "auth":
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
    print(f"[Production Circuit] installed max_attempts={max_attempts} budget_seconds={budget_seconds:.1f}", flush=True)


def apply() -> None:
    """Enable production mode on the canonical router module exactly once."""
    if getattr(router, "_PRODUCTION_POLICY_APPLIED", False):
        return
    chain = build_production_chain(router)
    if not chain:
        raise RuntimeError("Production model registry produced an empty provider chain")
    router._CHAIN_CACHE = list(chain)
    router._PRODUCTION_POLICY_APPLIED = True
    _install_production_circuit_breaker()
    print("[Production Model Registry] chain=" + ", ".join(name for name, _ in chain), flush=True)
