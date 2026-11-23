"""Production-only LLM routing policy with bounded, quota-aware failover."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import requests

import src.llm_router_light as router
from src.free_model_registry import build_production_chain
from src.state_io import load_json_state

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
HEALTH_PATH = ROOT / "data" / "llm_health.json"
# Keep one slow upstream response from disabling the primary selector for the
# rest of a run. The request timeout stays bounded; two consecutive read timeouts
# or a connection/gateway failure open the process-local circuit.
_OMNIROUTE_CIRCUIT_OPEN = False
_OMNIROUTE_READ_TIMEOUT_STREAK = 0

# OpenRouter's free-model daily request cap is account/API-key scoped and even
# failed requests consume it. Read the provider's authoritative counter before
# each direct :free request and reserve locally between refreshes.
_OPENROUTER_QUOTA_LOCK = threading.RLock()
_OPENROUTER_FREE_REPORTED_REMAINING: int | None = None
_OPENROUTER_FREE_REPORTED_USED: int | None = None
_OPENROUTER_FREE_RESERVED = 0
_OPENROUTER_FREE_CACHED_REMAINING: int | None = None
_OPENROUTER_FREE_QUOTA_REFRESHED_AT = 0.0
_OPENROUTER_FREE_QUOTA_CACHE_SECONDS = 8.0
_OPENROUTER_FREE_REQUEST_TIMESTAMPS: deque[float] = deque()
_OPENROUTER_FREE_RPM_LIMIT = 20
_OPENROUTER_FREE_BLOCKED_UNTIL = 0.0
# OpenRouter can proxy several model IDs through the same upstream provider
# pool. A shared-pool 429 should quarantine that model namespace for the rest
# of this run, without disabling unrelated upstreams or the whole OpenRouter key.
_OPENROUTER_DISABLED_NAMESPACES: set[str] = set()
_OMNIROUTE_CIRCUIT_RETRY_AT = 0.0
_OMNIROUTE_CIRCUIT_FAILURES = 0

_PROVIDER_QUOTA_PATTERNS = re.compile(r"(?:free-models-per-day|x-ratelimit-(?:remaining|reset).*?(?:0|quota)|account[_ -]?limit|daily[_ -]?quota|quota.*(?:exhaust|deplet)|(?:requests?|tokens?)/(?:day|daily)|provider.*(?:quota|limit)|\bTPD\b|tokens?\s+per\s+day|requests?\s+per\s+day|insufficient.*(?:credit|balance))", re.IGNORECASE)
# NaraRouter's telegram_required response is an account-level access block,
# not a model-specific 403. Classify this exact marker as provider-wide auth so
# production failover stops retrying NaraRouter for every candidate in the run.
_PROVIDER_AUTH_PATTERNS = re.compile(
    r"(?:\b401\b|unauthorized|invalid.*(?:api|credential|key|token)|"
    r"authentication.*(?:failed|error)|telegram_required)",
    re.IGNORECASE,
)
_KIRAAI_WALLET_PATTERN = re.compile(r"(?:insufficient.*(?:vnd|wallet|balance)|wallet.*balance|vnd.*balance)", re.IGNORECASE)


def _openrouter_namespace(deployment_id: str) -> str:
    """Return the OpenRouter model namespace (e.g. google, nvidia)."""
    if router._provider_family(deployment_id) != "openrouter":
        return ""
    model_id = str(deployment_id or "").split(":", 1)[1] if ":" in str(deployment_id or "") else ""
    return model_id.split("/", 1)[0].strip().casefold() if "/" in model_id else ""


def _is_provider_quota(message: str) -> bool:
    text = str(message or "")
    if re.search(r"upstream_provider_shared_pool|free-models-per-minute", text, re.IGNORECASE):
        return False
    if re.search(r"\b402\b", text):
        return True
    if "cloudflare workers ai" in text.casefold() and re.search(r"\b429\b|neurons?|daily|quota|free usage", text, re.I):
        return True
    return bool(_PROVIDER_QUOTA_PATTERNS.search(text))


def _is_provider_auth(message: str) -> bool:
    text = str(message or "")
    if "cloudflare workers ai" in text.casefold() and re.search(r"\b403\b", text):
        return True
    return bool(_PROVIDER_AUTH_PATTERNS.search(text))


def _is_kira_wallet_only(message: str, family: str) -> bool:
    return family == "kiraai" and bool(_KIRAAI_WALLET_PATTERN.search(str(message or "")))


def _provider_retry_after_seconds(message: str) -> float:
    """Extract provider reset hints, including compound values, without guessing."""
    text = str(message or "")
    match = re.search(
        r"(?:try again in|retry[-_ ]after\s*[:=]?)\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*(ms|s|sec|seconds?)\b",
        text,
        re.IGNORECASE,
    )
    if match:
        value = float(match.group(1))
        return max(0.0, value / 1000.0 if match.group(2).lower() == "ms" else value)

    compound = re.search(
        r"(?:(?P<h>\d+(?:\.\d+)?)\s*h\s*)?"
        r"(?:(?P<m>\d+(?:\.\d+)?)\s*m\s*)?"
        r"(?:(?P<s>\d+(?:\.\d+)?)\s*s)",
        text,
        re.IGNORECASE,
    )
    if compound and any(compound.group(k) for k in ("h", "m", "s")):
        return (
            float(compound.group("h") or 0) * 3600.0
            + float(compound.group("m") or 0) * 60.0
            + float(compound.group("s") or 0)
        )
    return 0.0


def _rate_limit_retry_delay(message: str, *, max_seconds: float = 8.0) -> float:
    """Extract a provider-supplied short retry delay, capped for production budget."""
    return min(_provider_retry_after_seconds(message), max_seconds)


def _openrouter_free_request_allowed(deployment_id: str) -> bool:
    """Fail closed unless OpenRouter confirms free-model daily headroom.

    Only model variants explicitly suffixed ':free' are admitted. The live
    /api/v1/key counter is authoritative; local reservations account for calls
    made since the last refresh, including failed attempts.
    """
    global _OPENROUTER_FREE_REPORTED_REMAINING, _OPENROUTER_FREE_REPORTED_USED
    global _OPENROUTER_FREE_RESERVED, _OPENROUTER_FREE_CACHED_REMAINING
    global _OPENROUTER_FREE_QUOTA_REFRESHED_AT
    global _OPENROUTER_FREE_BLOCKED_UNTIL

    if router._provider_family(deployment_id) != "openrouter":
        return True
    model_id = str(deployment_id).split(":", 1)[1] if ":" in str(deployment_id) else ""
    if not model_id.endswith(":free"):
        print(
            f"[Free Quota Guard] skipped={deployment_id} reason=openrouter_model_not_explicitly_free",
            flush=True,
        )
        return False

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print(
            f"[Free Quota Guard] skipped={deployment_id} reason=openrouter_key_missing",
            flush=True,
        )
        return False

    with _OPENROUTER_QUOTA_LOCK:
        now = time.monotonic()
        if now < _OPENROUTER_FREE_BLOCKED_UNTIL:
            print(
                f"[Free Quota Guard] skipped={deployment_id} "
                f"reason=provider_minute_cooldown remaining={_OPENROUTER_FREE_BLOCKED_UNTIL - now:.1f}s",
                flush=True,
            )
            return False
        if _OPENROUTER_FREE_BLOCKED_UNTIL:
            _OPENROUTER_FREE_BLOCKED_UNTIL = 0.0
        while _OPENROUTER_FREE_REQUEST_TIMESTAMPS and now - _OPENROUTER_FREE_REQUEST_TIMESTAMPS[0] >= 60.0:
            _OPENROUTER_FREE_REQUEST_TIMESTAMPS.popleft()
        if len(_OPENROUTER_FREE_REQUEST_TIMESTAMPS) >= _OPENROUTER_FREE_RPM_LIMIT:
            print(
                f"[Free Quota Guard] skipped={deployment_id} reason=free_model_20_rpm_cap_reached",
                flush=True,
            )
            return False
        refresh = (
            _OPENROUTER_FREE_CACHED_REMAINING is None
            or now - _OPENROUTER_FREE_QUOTA_REFRESHED_AT >= _OPENROUTER_FREE_QUOTA_CACHE_SECONDS
        )
        if refresh:
            try:
                response = requests.get(
                    "https://openrouter.ai/api/v1/key",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=4.0,
                )
                if response.status_code >= 400:
                    raise RuntimeError(f"OpenRouter key quota endpoint HTTP {response.status_code}")
                payload = response.json()
                quota = ((payload.get("data") or {}).get("free_model_daily_requests") or {})
                remaining_value = quota.get("remaining")
                if remaining_value is None:
                    raise ValueError("OpenRouter key response omitted free_model_daily_requests.remaining")
                remote_remaining = max(0, int(remaining_value))
                used_value = quota.get("used")
                remote_used = max(0, int(used_value)) if used_value is not None else None
                daily_reset = (
                    remote_used is not None
                    and _OPENROUTER_FREE_REPORTED_USED is not None
                    and remote_used < _OPENROUTER_FREE_REPORTED_USED
                )
                if daily_reset:
                    # The provider's UTC-day counter reset. Yesterday's local
                    # reservations and RPM history must not reduce today's cap.
                    _OPENROUTER_FREE_RESERVED = 0
                    _OPENROUTER_FREE_REQUEST_TIMESTAMPS.clear()
                    unreflected_reservations = 0
                elif remote_used is not None and _OPENROUTER_FREE_REPORTED_USED is not None:
                    remotely_observed = max(0, remote_used - _OPENROUTER_FREE_REPORTED_USED)
                    unreflected_reservations = max(0, _OPENROUTER_FREE_RESERVED - remotely_observed)
                else:
                    # If the account endpoint omits used, retain local reservations;
                    # a larger daily ceiling alone does not prove they were counted.
                    unreflected_reservations = _OPENROUTER_FREE_RESERVED
                _OPENROUTER_FREE_REPORTED_REMAINING = remote_remaining
                if remote_used is not None:
                    _OPENROUTER_FREE_REPORTED_USED = remote_used
                _OPENROUTER_FREE_RESERVED = unreflected_reservations
                _OPENROUTER_FREE_CACHED_REMAINING = max(
                    0,
                    remote_remaining - unreflected_reservations,
                )
                _OPENROUTER_FREE_QUOTA_REFRESHED_AT = now
                print(
                    "[Free Quota Guard] provider=openrouter "
                    f"used={quota.get('used', 'unknown')} "
                    f"limit={quota.get('limit', 'unknown')} "
                    f"remaining={_OPENROUTER_FREE_CACHED_REMAINING} "
                    "scope=api_key_daily",
                    flush=True,
                )
            except Exception as exc:
                # Unknown quota is not permission to spend. Other providers
                # remain eligible; OpenRouter is skipped until a later preflight.
                _OPENROUTER_FREE_CACHED_REMAINING = 0
                _OPENROUTER_FREE_QUOTA_REFRESHED_AT = now
                logger.warning("OpenRouter free quota preflight unavailable: %s", exc)
                print(
                    f"[Free Quota Guard] skipped={deployment_id} "
                    f"reason=preflight_unavailable error={type(exc).__name__}",
                    flush=True,
                )
                return False

        remaining = int(_OPENROUTER_FREE_CACHED_REMAINING or 0)
        if remaining <= 0:
            print(
                f"[Free Quota Guard] skipped={deployment_id} reason=daily_free_request_cap_reached",
                flush=True,
            )
            return False

        _OPENROUTER_FREE_CACHED_REMAINING = remaining - 1
        _OPENROUTER_FREE_RESERVED += 1
        _OPENROUTER_FREE_REQUEST_TIMESTAMPS.append(now)
        print(
            f"[Free Quota Guard] reserved=1 deployment={deployment_id} "
            f"remaining_local={_OPENROUTER_FREE_CACHED_REMAINING}",
            flush=True,
        )
        return True


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
    # A persisted quota cooldown is authoritative until its actual reset.
    # Never half-open probe a future disabled_until: free-tier 429s consume
    # quota and the next valid attempt must wait for the provider reset window.
    return bool(model_disabled or provider_disabled)


def _omniroute_structured_json_ok(content: str) -> bool:
    raw = str(content or '').strip()
    try:
        return isinstance(json.loads(raw), dict)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False


_OMNIROUTE_PROVIDER_LABELS = {
    "groq": "Groq",
    "openrouter": "OpenRouter",
    "nara": "NaraRouter",
    "nararouter": "NaraRouter",
    "mistral": "Mistral",
    "nvidia": "NVIDIA",
    "sambanova": "SambaNova",
    "llm7": "LLM7",
    "anyapi": "AnyAPI",
    "api-airforce": "API Airforce",
    "cloudflare-ai": "Cloudflare AI",
    "huggingface": "HuggingFace",
    "hf": "HuggingFace",
    "kiraai": "KiraAI",
}


def _omniroute_result_provider(selected: str, decision: str) -> str:
    """Return upstream provider family when OmniRoute exposes it in decision metadata.

    A generic OmniRoute:model identity does not let recovery recognize which
    provider family actually generated the draft, so the repair path can retry
    that same family instead of using an independent fallback. Without explicit
    metadata, retain the generic label rather than guessing from the model name.
    """
    match = re.search(
        r"(?:^|[;,\s])provider\s*=\s*([a-z0-9_-]+)",
        str(decision or ""),
        re.IGNORECASE,
    )
    family = match.group(1).casefold() if match else ""
    label = _OMNIROUTE_PROVIDER_LABELS.get(family)
    model = str(selected or "").strip()
    if label and model:
        return f"{label}:{model}"
    return f"OmniRoute:{model}"


def _omniroute_call(system_prompt, user_content):
    """Try OmniRoute first, then bypass a transport-unhealthy gateway for this run.

    OmniRoute is the primary selector when healthy. A transport failure opens a
    process-local circuit so later candidates use the independent provider chain
    rather than repeatedly waiting for a gateway that has already timed out.
    """
    global _OMNIROUTE_CIRCUIT_OPEN, _OMNIROUTE_READ_TIMEOUT_STREAK
    global _OMNIROUTE_CIRCUIT_RETRY_AT, _OMNIROUTE_CIRCUIT_FAILURES
    base_url = os.getenv("OMNIROUTE_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        return None, None
    if _OMNIROUTE_CIRCUIT_OPEN:
        remaining = _OMNIROUTE_CIRCUIT_RETRY_AT - time.monotonic()
        if remaining > 0:
            print(
                f"[OmniRoute Circuit] skipped=1 reason=open_cooldown remaining={remaining:.1f}s; using hard fallback",
                flush=True,
            )
            return None, None
        # Half-open: after a short, bounded cooldown, allow this call to probe
        # the free-only route again. Success closes the circuit; another
        # upstream-pool failure applies a bounded exponential backoff.
        _OMNIROUTE_CIRCUIT_OPEN = False
        print("[OmniRoute Circuit] half_open_probe=1 reason=cooldown_elapsed", flush=True)
    api_key = os.getenv("OMNIROUTE_API_KEY", "").strip()
    model = os.getenv("OMNIROUTE_MODEL", "auto/best-free").strip() or "auto/best-free"
    api_base = base_url if base_url.endswith("/v1") else f"{base_url}/v1"
    url = f"{api_base}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.15,
        # OmniRoute v3.8.50 supports OpenAI-compatible structured output. Request
        # JSON mode explicitly instead of relying only on prompt wording; the
        # existing strict parser still rejects any malformed/non-object result.
        "response_format": {"type": "json_object"},
        "max_tokens": max(256, int(os.getenv("RADAR_LLM_MAX_TOKENS", "700") or 700)),
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    timeout = max(0.5, min(12.0, float(os.getenv("OMNIROUTE_TIMEOUT_SECONDS", "12") or 12)))
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
        if not _omniroute_structured_json_ok(content):
            raise RuntimeError("OmniRoute returned invalid structured JSON; response rejected before editorial pipeline")
        _OMNIROUTE_READ_TIMEOUT_STREAK = 0
        _OMNIROUTE_CIRCUIT_OPEN = False
        _OMNIROUTE_CIRCUIT_RETRY_AT = 0.0
        _OMNIROUTE_CIRCUIT_FAILURES = 0
        decision = response.headers.get("X-OmniRoute-Decision", "")
        selected = str(data.get("model") or decision or model)
        print(
            f"[OmniRoute Primary] success=true requested={model} selected={selected} "
            f"decision={decision[:300]}",
            flush=True,
        )
        provider_label = _omniroute_result_provider(selected, decision)
        print(f"[OmniRoute Primary] upstream_identity={provider_label}", flush=True)
        return content, provider_label
    except Exception as exc:
        if isinstance(exc, requests.ReadTimeout):
            _OMNIROUTE_READ_TIMEOUT_STREAK += 1
            transport_failure = _OMNIROUTE_READ_TIMEOUT_STREAK >= 2
            if not transport_failure:
                print(
                    "[OmniRoute Circuit] read_timeout_streak=1/2; keep gateway available for one bounded retry",
                    flush=True,
                )
        else:
            # Only consecutive read timeouts count as a potentially transient slow
            # upstream. Connection failures and gateway 5xx responses still trip
            # the circuit immediately; non-transport failures reset the streak.
            _OMNIROUTE_READ_TIMEOUT_STREAK = 0
            transport_failure = isinstance(exc, requests.Timeout | requests.ConnectionError) or bool(
                re.search(r"\bHTTP (?:502|503|504)\b", str(exc), re.IGNORECASE)
            )
        if transport_failure:
            _OMNIROUTE_CIRCUIT_FAILURES += 1
            _OMNIROUTE_CIRCUIT_OPEN = True
            status_match = re.search(r"HTTP\s+(502|503|504)", str(exc), re.IGNORECASE)
            if status_match:
                # A 502/503/504 from auto/best-free may mean its model pool is
                # temporarily out of quota, not that the local gateway died.
                cooldown = min(30.0, 2.0 ** min(_OMNIROUTE_CIRCUIT_FAILURES, 4))
                failure_kind = f"free_upstream_pool_http_{status_match.group(1)}"
            elif isinstance(exc, requests.ReadTimeout):
                cooldown = min(45.0, 8.0 * (2 ** min(_OMNIROUTE_CIRCUIT_FAILURES - 1, 2)))
                failure_kind = "read_timeout"
            else:
                cooldown = min(60.0, 15.0 * (2 ** min(_OMNIROUTE_CIRCUIT_FAILURES - 1, 2)))
                failure_kind = "transport_failure"
            _OMNIROUTE_CIRCUIT_RETRY_AT = time.monotonic() + cooldown
            print(
                f"[OmniRoute Circuit] opened=1 reason={failure_kind} cooldown={cooldown:.1f}s "
                "subsequent calls bypass gateway until half-open probe",
                flush=True,
            )
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
    max_tokens = max(256, int(os.getenv("RADAR_LLM_MAX_TOKENS", "950") or 950))

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
            global _OPENROUTER_FREE_BLOCKED_UNTIL
            deployment_id = deployment["model_info"]["id"]
            family = router._provider_family(deployment_id)
            namespace = _openrouter_namespace(deployment_id)
            if family == "openrouter" and namespace in _OPENROUTER_DISABLED_NAMESPACES:
                print(
                    f"[Production Circuit] skipped={deployment_id} "
                    f"reason=upstream_namespace_quarantined namespace={namespace}",
                    flush=True,
                )
                return None
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
            if family == "openrouter" and not _openrouter_free_request_allowed(deployment_id):
                if (
                    int(_OPENROUTER_FREE_CACHED_REMAINING or 0) <= 0
                    or time.monotonic() < _OPENROUTER_FREE_BLOCKED_UNTIL
                    or len(_OPENROUTER_FREE_REQUEST_TIMESTAMPS) >= _OPENROUTER_FREE_RPM_LIMIT
                ):
                    skipped_families.add("openrouter")
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
                elif family == "openrouter" and re.search(r"upstream_provider_shared_pool", message, re.I):
                    # Multiple model IDs can share the same upstream provider
                    # pool (e.g. Google-hosted Gemma variants). Keep the failure
                    # model/namespace scoped: other OpenRouter namespaces remain
                    # eligible, but sibling variants do not burn more quota.
                    namespace = _openrouter_namespace(deployment_id)
                    if namespace:
                        _OPENROUTER_DISABLED_NAMESPACES.add(namespace)
                    router._disable(deployment_id, "rate_limit")
                    scope = "model"
                elif family == "openrouter" and re.search(r"free-models-per-minute", message, re.I):
                    # This is an API-key-wide short window, not a daily quota.
                    # Do not permanently disable the family; a timed local guard
                    # will reopen the free pool at the provider's reset time.
                    skipped_families.add(family)
                    with router._STATE_LOCK:
                        router._DISABLED.add(deployment_id)
                    router._disable(deployment_id, "rate_limit")
                    scope = "provider"
                elif _is_provider_auth(message) or (
                    _is_provider_quota(message)
                    and router._provider_quota_is_family_scoped(family, reason, message)
                ):
                    skipped_families.add(family)
                    with router._STATE_LOCK:
                        router._DISABLED_FAMILIES.add(family)
                        router._DISABLED.add(deployment_id)
                    router._disable(deployment_id, reason)
                    scope = "provider"
                else:
                    router._disable(deployment_id, reason)
                    scope = "model"

                if reason in {"quota", "rate_limit"}:
                    retry_after = _provider_retry_after_seconds(message)
                    if retry_after <= 0:
                        if family == "openrouter" and re.search(r"upstream_provider_shared_pool", message, re.I):
                            # Shared upstream pools commonly return 429 without
                            # a useful Retry-After header. Use a bounded five-minute
                            # model cooldown; namespace quarantine lasts for this run.
                            retry_after = 300.0
                        elif family == "openrouter" and re.search(r"free-models-per-day|daily", message, re.I):
                            now_utc = datetime.now(timezone.utc)
                            next_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 86400
                            retry_after = max(60.0, next_day - time.time())
                        elif family == "groq" and re.search(r"\bTPD\b|tokens?\s+per\s+day|requests?\s+per\s+day", message, re.I):
                            # Groq's daily token window resets daily; when the
                            # response has no explicit reset header, use the next
                            # UTC midnight rather than a rolling 24-hour delay.
                            now_utc = datetime.now(timezone.utc)
                            next_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 86400
                            retry_after = max(5.0, next_day - time.time())
                        elif family == "cloudflare-ai" and re.search(r"neurons?|daily|quota|free usage|usage limit", message, re.I):
                            # Workers AI's free allocation is account-wide and
                            # resets at 00:00 UTC. Persist a provider cooldown until
                            # that reset instead of retrying sibling models.
                            now_utc = datetime.now(timezone.utc)
                            next_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 86400
                            retry_after = max(5.0, next_day - time.time())
                        else:
                            retry_after = 60.0
                    if family == "cloudflare-ai" and re.search(
                        r"neurons?|daily|quota|free usage|usage limit", message, re.I
                    ):
                        # A daily Workers AI free-allocation error always resets
                        # at 00:00 UTC; do not let a short generic Retry-After
                        # reopen the account before the documented reset.
                        now_utc = datetime.now(timezone.utc)
                        next_day = (
                            now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
                            .timestamp()
                            + 86400
                        )
                        retry_after = max(5.0, next_day - time.time())
                    retry_after = max(5.0, min(retry_after, 86400.0))
                    cooldown_target = family if scope == "provider" else deployment_id
                    disabled_until = time.time() + retry_after
                    daily_window = retry_after >= 3600.0 or (
                        family == "openrouter" and re.search(r"free-models-per-day|daily", message, re.I)
                    ) or (
                        family == "groq" and re.search(r"\bTPD\b|tokens?\s+per\s+day|requests?\s+per\s+day", message, re.I)
                    ) or (
                        family == "cloudflare-ai" and re.search(r"neurons?|daily|quota|free usage|usage limit", message, re.I)
                    )
                    quota_window = "daily" if daily_window else "minute"
                    # The in-process router must observe the same provider reset
                    # as the persisted health file. Otherwise mission recovery can
                    # clear a short generic cooldown and hit a still-exhausted
                    # daily free model again before its actual reset.
                    if scope == "model":
                        with router._STATE_LOCK:
                            router._MODEL_DISABLED_UNTIL[deployment_id] = max(
                                router._MODEL_DISABLED_UNTIL.get(deployment_id, 0.0),
                                time.monotonic() + retry_after,
                            )
                            router._MODEL_DISABLED_REASON[deployment_id] = (
                                "quota" if quota_window == "daily" else "rate_limit"
                            )
                            router._DISABLED.add(deployment_id)
                    if family == "openrouter" and scope == "provider" and quota_window == "minute":
                        with _OPENROUTER_QUOTA_LOCK:
                            _OPENROUTER_FREE_BLOCKED_UNTIL = time.monotonic() + retry_after
                    print(
                        f"[Quota Cooldown] scope={scope} target={cooldown_target} "
                        f"disabled_until={disabled_until:.3f} delay_seconds={retry_after:.1f} "
                        f"window={quota_window} reason={reason}",
                        flush=True,
                    )

                print(
                    f"[Production Circuit] failed={deployment_id} reason={reason} scope={scope}: "
                    f"exception={type(exc).__name__} provider={family} model={deployment_id} {message}",
                    flush=True,
                )
                return None

        # OmniRoute is the first model-selection layer when configured. Production
        # explicitly requests auto/best-free: paid/cheap/premium tiers are not
        # eligible, and exhausted free-provider quotas fall through within that
        # free-only candidate pool. The local registry remains the hard fallback.
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
        if os.getenv("RADAR_ENABLE_OPENROUTER_FREE_ROUTER", "0").strip().lower() in {"1", "true", "yes"} and os.getenv("OPENROUTER_API_KEY"):
            emergency_fallbacks.append(("OpenRouterFreeRouter", router._openrouter_free_router))
        if os.getenv("RADAR_ENABLE_HF_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and os.getenv("HF_TOKEN"):
            emergency_fallbacks.append(("HuggingFace", router._huggingface))

        for emergency_name, emergency_fn in emergency_fallbacks:
            # Emergency fallbacks obey the same health policy as primary deployments.
            emergency_health_ids = {
                "OpenRouterFreeRouter": "openrouter:free-router",
                "HuggingFace": f"huggingface:{(os.getenv('HF_MODEL') or 'inference').strip()}",
            }
            deployment_id = emergency_health_ids.get(emergency_name)
            family = router._provider_family(deployment_id) if deployment_id else ""
            if family in skipped_families or family in router._DISABLED_FAMILIES:
                print(f"[Production Circuit] skipped={deployment_id or emergency_name} reason=provider_disabled", flush=True)
                continue
            if deployment_id and _persistently_unavailable(deployment_id, recovery_probe=attempts > 0):
                print(f"[Production Circuit] skipped={deployment_id} reason=persisted_health", flush=True)
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            emergency_limit = 6.0
            try:
                print(f"[Production Circuit] {emergency_name.lower()}_emergency_attempt=1", flush=True)
                future = router._CALL_EXECUTOR.submit(emergency_fn, system_prompt, user_content)
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
