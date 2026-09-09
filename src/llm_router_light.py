"""Production LLM router with deterministic registry-driven failover."""
from __future__ import annotations

import concurrent.futures
import os
import re
import threading
import time

import requests

_CALL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-call")

class QuotaExceeded(Exception):
    """Provider-side quota, auth, permission, or availability failure."""

_DISABLED: set[str] = set()
_DISABLED_FAMILIES: set[str] = set()
_MODEL_DISABLED_UNTIL: dict[str, float] = {}
_STATE_LOCK = threading.RLock()
_CHAIN_CACHE = None
_PRODUCTION_POLICY_APPLIED = False
_PROVIDER_TIMEOUTS = {"Groq:": 8.0, "OpenRouter:": 7.0, "Gemini": 8.0, "HuggingFace": 5.0}
_REQUEST_TIMEOUT = 10
_ROUTER_BUDGET_SECONDS = 24
_MAX_TRANSIENT_RETRIES = 1
_MODEL_COOLDOWN_SECONDS = {"quota": 12.0, "model": 45.0, "transient": 10.0, "other": 15.0}
GEMINI_DEFAULT_MODEL = "gemini-3.7-flash"


def _provider_family(name: str) -> str:
    return str(name or "").split(":", 1)[0].strip().casefold()


def _provider_credential_available(name: str) -> bool:
    env = {"groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY", "gemini": "GEMINI_API_KEY", "huggingface": "HF_TOKEN"}.get(_provider_family(name))
    return bool(os.getenv(env)) if env else True


def _extract_message(payload: dict):
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("LLM response has no choices")
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") or {}
    if isinstance(message, dict) and message.get("content") is not None:
        return message["content"]
    if choice.get("text") is not None:
        return choice["text"]
    raise ValueError("LLM response content not found")


def _groq(system_prompt, user_content, model, *, output_mode="native"):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], "max_completion_tokens": 850, "stream": False, "temperature": 0.15}
    if output_mode == "native":
        payload["response_format"] = {"type": "json_object"}
    if model.startswith("qwen/"):
        payload.update({"reasoning_effort": "none", "reasoning_format": "hidden"})
    elif model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=_REQUEST_TIMEOUT)
    if r.status_code in (401, 402, 403, 404, 429):
        raise QuotaExceeded(f"Groq {model}: HTTP {r.status_code} {r.text[:400]}")
    r.raise_for_status()
    return _extract_message(r.json())


def _openrouter_supports_response_format(model: str) -> bool:
    try:
        from free_model_registry import model_capability
        return bool(model_capability(model).get("response_format"))
    except Exception:
        return False


def _openrouter(system_prompt, user_content, model, *, output_mode="native"):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], "max_tokens": 850, "temperature": 0.15}
    if output_mode == "native" and _openrouter_supports_response_format(model):
        payload["response_format"] = {"type": "json_object"}
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/jamshidimoh/AI-Future-Radar", "X-Title": "AI Future Radar"}, json=payload, timeout=_REQUEST_TIMEOUT)
    body = r.text[:800]
    if r.status_code in (401, 403, 404, 429):
        raise QuotaExceeded(f"OpenRouter {model}: HTTP {r.status_code} {body}")
    if r.status_code == 402:
        raise QuotaExceeded(f"OpenRouter {model}: HTTP 402 account_limit {body}")
    r.raise_for_status()
    return _extract_message(r.json())


def _gemini(system_prompt, user_content):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    from google import genai
    from google.genai import types
    model = (os.getenv("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL).strip()
    client = genai.Client(api_key=key, http_options={"timeout": 8_000})
    try:
        response = client.models.generate_content(model=model, contents=user_content, config=types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json", max_output_tokens=850))
        return response.text
    except Exception as exc:
        raise QuotaExceeded(f"Gemini {model}: {exc}") from exc


def _hf_price_is_free(item):
    p = item.get("pricing") or {}
    try:
        return float(p.get("input", -1)) == 0 and float(p.get("output", -1)) == 0
    except (TypeError, ValueError):
        return False


def _discover_hf_models():
    try:
        token = os.getenv("HF_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = requests.get("https://router.huggingface.co/v1/models", headers=headers, timeout=10)
        if r.status_code in (401, 403):
            raise QuotaExceeded(f"HF discovery unauthorized: HTTP {r.status_code}")
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("data", payload if isinstance(payload, list) else [])
        return [x for x in rows if isinstance(x, dict) and x.get("id")]
    except QuotaExceeded:
        raise
    except Exception:
        return []


def _select_hf_model(models=None):
    """Return a current free HF chat model, preserving legacy test API."""
    rows = list(models) if isinstance(models, list) else _discover_hf_models()
    free = [m for m in rows if isinstance(m, dict) and _hf_price_is_free(m)]
    explicit = (os.getenv("HF_MODEL") or "").strip()
    if explicit and any(m.get("id") == explicit for m in free):
        return explicit
    if not free:
        raise QuotaExceeded("No zero-price Hugging Face chat model is currently available")
    return str(free[0].get("id"))


def _huggingface(system_prompt, user_content):
    token = os.getenv("HF_TOKEN")
    if not token:
        return None
    from huggingface_hub import InferenceClient
    model = _select_hf_model()
    response = InferenceClient(token=token, provider="auto").chat.completions.create(model=model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], max_tokens=850)
    return response.choices[0].message.content


def get_quality_chain():
    global _CHAIN_CACHE
    if _CHAIN_CACHE is not None:
        return list(_CHAIN_CACHE)
    from free_model_registry import build_production_chain
    chain = build_production_chain(__import__(__name__))
    _CHAIN_CACHE = list(chain)
    print("[Light Router] chain=" + ", ".join(n for n, _ in chain), flush=True)
    return list(_CHAIN_CACHE)


def _failure_class(message: str) -> str:
    text = str(message or "").lower()
    if re.search(r"\b401\b|unauthenticated|invalid.*(?:credential|key|token)|unauthorized|authentication.*(?:fail|invalid)", text):
        return "auth"
    if re.search(r"\b403\b|permission|model.*(?:blocked|disabled|unavailable)|not found", text) and not re.search(r"authentication|invalid.*(?:credential|key|token)", text):
        return "model"
    if re.search(r"\b402\b|\b429\b|quota|rate.?limit|resource_exhausted|payment required|depleted your monthly included credits", text):
        return "quota"
    if re.search(r"\b(?:408|500|502|503|504)\b|timeout|timed out|temporarily unavailable|connection", text):
        return "transient"
    if re.search(r"\b400\b|invalid.*(?:request|parameter)|unsupported.*(?:parameter|response_format)", text):
        return "model"
    return "other"


def _should_disable_provider(message: str) -> bool:
    """Compatibility classifier; routing itself uses model/family semantics below."""
    return bool(re.search(r"\b(?:401|402|403|404|408|429|500|502|503|504)\b", str(message or "")))


def _disable(name: str, reason: str) -> None:
    family = _provider_family(name)
    with _STATE_LOCK:
        _DISABLED.add(name)
        if reason == "auth":
            _DISABLED_FAMILIES.add(family)
        elif reason == "quota" and not _PRODUCTION_POLICY_APPLIED and family != "openrouter":
            _DISABLED_FAMILIES.add(family)
        elif reason in _MODEL_COOLDOWN_SECONDS:
            _MODEL_DISABLED_UNTIL[name] = max(float(_MODEL_DISABLED_UNTIL.get(name, 0.0) or 0.0), time.monotonic() + _MODEL_COOLDOWN_SECONDS[reason])
    scope = "family" if reason == "auth" or (reason == "quota" and not _PRODUCTION_POLICY_APPLIED and family != "openrouter") else "model"
    print(f"[Light Router] disabled={name} family={family} reason={reason} scope={scope}", flush=True)


def _model_is_disabled(name: str) -> bool:
    with _STATE_LOCK:
        until = float(_MODEL_DISABLED_UNTIL.get(name, 0.0) or 0.0)
        if until and until <= time.monotonic():
            _MODEL_DISABLED_UNTIL.pop(name, None)
            return False
        return until > time.monotonic()


def _provider_timeout(name: str, remaining: float) -> float:
    for prefix, limit in _PROVIDER_TIMEOUTS.items():
        if name.startswith(prefix):
            return max(0.1, min(remaining, limit))
    return max(0.1, min(remaining, 4.0))


def _invoke(fn, system_prompt, user_content):
    return fn(system_prompt, user_content)


def call_llm_with_fallback(system_prompt, user_content, providers=None):
    providers = providers or get_quality_chain()
    last = None
    deadline = time.monotonic() + _ROUTER_BUDGET_SECONDS
    retries: dict[str, int] = {}
    local_models: set[str] = set()
    local_families: set[str] = set()

    for name, fn in providers:
        family = _provider_family(name)
        if name in local_models or family in local_families or family in _DISABLED_FAMILIES:
            continue
        if _model_is_disabled(name):
            print(f"[Light Router] skipped={name} reason=model_cooldown", flush=True)
            continue
        if not _provider_credential_available(name):
            print(f"[Light Router] skipped={name} reason=missing_credential", flush=True)
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        timeout = _provider_timeout(name, remaining)
        future = _CALL_EXECUTOR.submit(_invoke, fn, system_prompt, user_content)
        try:
            result = future.result(timeout=timeout)
            if result:
                print(f"[Light Router] success={name}", flush=True)
                return result, name
        except concurrent.futures.TimeoutError:
            last = TimeoutError(f"{name}: exceeded provider timeout of {timeout:.1f}s")
            local_models.add(name)
            _disable(name, "transient")
        except QuotaExceeded as exc:
            last = exc
            reason = _failure_class(str(exc))
            local_models.add(name)
            if reason == "auth":
                local_families.add(family)
            elif reason == "quota" and family == "openrouter" and re.search(r"\b402\b|account_limit|requests?/day|daily|free.*tier", str(exc), re.I):
                local_families.add(family)
                with _STATE_LOCK:
                    _DISABLED_FAMILIES.add(family)
            _disable(name, reason)
        except Exception as exc:
            last = exc
            reason = _failure_class(str(exc))
            if reason == "auth":
                local_families.add(family)
                _disable(name, reason)
            elif reason == "transient" and retries.get(name, 0) < _MAX_TRANSIENT_RETRIES:
                retries[name] = retries.get(name, 0) + 1
                try:
                    retry_future = _CALL_EXECUTOR.submit(_invoke, fn, system_prompt, user_content)
                    retry_result = retry_future.result(timeout=min(timeout, max(0.1, deadline - time.monotonic())))
                    if retry_result:
                        print(f"[Light Router] success={name} retry={retries[name]}", flush=True)
                        return retry_result, name
                except Exception as retry_exc:
                    last = retry_exc
                    retry_reason = _failure_class(str(retry_exc))
                    if retry_reason == "auth":
                        local_families.add(family)
                    _disable(name, retry_reason)
            else:
                local_models.add(name)
                _disable(name, reason)
        if deadline - time.monotonic() <= 0:
            break
    print(f"[Light Router] exhausted; last={last}", flush=True)
    return None, None
