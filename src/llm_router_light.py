"""Low-token, provider-diverse LLM router for production summarization.

Includes a bounded Hugging Face fallback. In free-first mode, paid HF models
are never selected.
"""
from __future__ import annotations

import concurrent.futures
import os
import re
import time

import requests

_CALL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-call")


class QuotaExceeded(Exception):
    """Provider-side quota, auth, or availability failure safe for failover."""


_DISABLED = set()
_DISABLED_FAMILIES = set()
_CHAIN_CACHE = None
_PROVIDER_TIMEOUTS = {"Groq:": 6.0, "OpenRouter:": 2.5, "Gemini": 10.0, "HuggingFace": 4.0}
_REQUEST_TIMEOUT = 8
_ROUTER_BUDGET_SECONDS = 14
_MAX_TRANSIENT_RETRIES = 1

GROQ_MODELS = ("qwen/qwen3.6-27b", "openai/gpt-oss-120b")
OPENROUTER_MODELS = ("openai/gpt-oss-120b:free", "openai/gpt-oss-20b:free")
GEMINI_DEFAULT_MODEL = "gemini-3.7-flash"
_HF_MODEL_CACHE = None
_HF_MODEL_CACHE_TS = 0.0
_HF_MODEL_CACHE_TTL = 900
CHINESE_FREE_PREFIXES = ("qwen/", "qwen3", "qwen3.", "z-ai/", "thudm/", "moonshotai/", "minimax/", "deepseek/")


def _provider_family(name: str) -> str:
    return str(name or "").split(":", 1)[0].strip().casefold()


def _extract_message(payload):
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("LLM response has no choices")
    choice = choices[0]
    if isinstance(choice, dict):
        message = choice.get("message") or {}
        if isinstance(message, dict) and message.get("content") is not None:
            return message["content"]
        if choice.get("text") is not None:
            return choice["text"]
    raise ValueError("LLM response content not found")


def _groq(system_prompt, user_content, model):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], "response_format": {"type": "json_object"}, "max_completion_tokens": 900, "stream": False}
    if model.startswith("qwen/"):
        payload.update({"reasoning_effort": "none", "reasoning_format": "hidden", "temperature": 0.15})
    elif model.startswith("openai/gpt-oss"):
        payload.update({"reasoning_effort": "low", "temperature": 0.15})
    else:
        payload.update({"temperature": 0.15})
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=_REQUEST_TIMEOUT)
    if r.status_code in (401, 402, 429):
        raise QuotaExceeded(f"Groq {model}: HTTP {r.status_code}")
    r.raise_for_status()
    return _extract_message(r.json())


def _openrouter(system_prompt, user_content, model):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json={"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], "response_format": {"type": "json_object"}, "max_tokens": 900, "temperature": 0.15}, timeout=_REQUEST_TIMEOUT)
    if r.status_code in (401, 402, 429):
        raise QuotaExceeded(f"OpenRouter {model}: HTTP {r.status_code}")
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
        response = client.models.generate_content(model=model, contents=user_content, config=types.GenerateContentConfig(system_instruction=system_prompt, response_mime_type="application/json", temperature=0.15, max_output_tokens=900))
        return response.text
    except Exception as exc:
        msg = str(exc).lower()
        if any(token in msg for token in ("401", "403", "404", "429", "quota", "resource_exhausted", "unauthenticated")):
            raise QuotaExceeded(f"Gemini {model}: {exc}") from exc
        raise


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _hf_price_is_free(item):
    pricing = item.get("pricing") or {}
    return isinstance(pricing, dict) and _num(pricing.get("input"), -1) == 0 and _num(pricing.get("output"), -1) == 0


def _hf_supported_as_chat(item):
    task = str(item.get("task") or "").lower()
    model_id = str(item.get("id") or "")
    blocked = {"text-to-image", "automatic-speech-recognition", "feature-extraction", "text-classification"}
    return bool(model_id) and task not in blocked


def _discover_hf_models():
    global _HF_MODEL_CACHE, _HF_MODEL_CACHE_TS
    now = time.time()
    if _HF_MODEL_CACHE is not None and now - _HF_MODEL_CACHE_TS < _HF_MODEL_CACHE_TTL:
        return _HF_MODEL_CACHE
    try:
        token = os.getenv("HF_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = requests.get("https://router.huggingface.co/v1/models", headers=headers, timeout=20)
        if response.status_code in (401, 403):
            raise QuotaExceeded(f"HF discovery unauthorized: HTTP {response.status_code}")
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", payload if isinstance(payload, list) else [])
        normalized = []
        for item in rows if isinstance(rows, list) else []:
            if not isinstance(item, dict) or not _hf_supported_as_chat(item):
                continue
            providers = item.get("providers") or item.get("inferenceProviderMapping") or []
            pricing = item.get("pricing") or {}
            normalized.append({"id": item.get("id"), "free": _hf_price_is_free(item), "providers": len(providers) if isinstance(providers, (list, dict)) else 0, "latency": _num(item.get("first_token_latency_ms"), 999999), "throughput": _num(item.get("throughput"), 0), "context": int(item.get("context_length") or 0), "structured": bool(item.get("supports_structured_output")), "input": _num(pricing.get("input"), 999999), "output": _num(pricing.get("output"), 999999)})
        _HF_MODEL_CACHE, _HF_MODEL_CACHE_TS = normalized, now
        print(f"[HF Router] models discovered: {len(normalized)}", flush=True)
        return normalized
    except QuotaExceeded:
        raise
    except Exception as exc:
        _HF_MODEL_CACHE, _HF_MODEL_CACHE_TS = [], now
        print(f"[HF Router] discovery failed: {exc}", flush=True)
        return []


def _select_hf_model():
    policy = (os.getenv("HF_POLICY") or "free-first").strip().lower()
    explicit = (os.getenv("HF_MODEL") or "").strip()
    models = _discover_hf_models()
    by_id = {m["id"]: m for m in models}
    if explicit and explicit in by_id:
        candidate = by_id[explicit]
        if policy != "free-first" or candidate["free"]:
            return explicit
    structured = [m for m in models if m["structured"]] or models
    if policy == "free-first":
        pool = [m for m in structured if m["free"]]
        if not pool:
            raise QuotaExceeded("No zero-price Hugging Face model is currently available")
        pool.sort(key=lambda m: (not any(str(m["id"]).lower().startswith(p) for p in CHINESE_FREE_PREFIXES), -(m["providers"] or 0), -(m["throughput"] or 0), m["latency"], -(m["context"] or 0)))
    else:
        pool = sorted(structured, key=lambda m: (not m["free"], -(m["providers"] or 0), m["latency"]))
    if not pool:
        raise QuotaExceeded("No Hugging Face chat model is available")
    selected = pool[0]
    print(f"[HF Router] selected: {selected['id']} | free={selected['free']}", flush=True)
    return selected["id"]


def _huggingface(system_prompt, user_content):
    token = os.getenv("HF_TOKEN")
    if not token:
        return None
    from huggingface_hub import InferenceClient
    model = _select_hf_model()
    try:
        client = InferenceClient(token=token, provider="auto")
        response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}], response_format={"type": "json_object"}, max_tokens=900)
    except Exception as exc:
        message = str(exc).lower()
        if any(token in message for token in ("402", "payment required", "depleted your monthly included credits", "429", "rate limit")):
            raise QuotaExceeded(f"Hugging Face quota/credits exhausted: {exc}") from exc
        raise
    return response.choices[0].message.content


def get_quality_chain():
    global _CHAIN_CACHE
    if _CHAIN_CACHE is not None:
        return list(_CHAIN_CACHE)
    chain = [(f"Groq:{model}", lambda sp, uc, m=model: _groq(sp, uc, m)) for model in GROQ_MODELS]
    chain.append(("Gemini", _gemini))
    chain.extend((f"OpenRouter:{model}", lambda sp, uc, m=model: _openrouter(sp, uc, m)) for model in OPENROUTER_MODELS)
    chain.append(("HuggingFace", _huggingface))
    _CHAIN_CACHE = list(chain)
    print("[Light Router] chain=" + ", ".join(name for name, _ in chain), flush=True)
    return list(_CHAIN_CACHE)


def _failure_class(message: str) -> str:
    text = str(message or "").lower()
    if re.search(r"\b(?:401|403|404|unauthenticated|authentication|invalid.*credential|invalid.*key)\b", text):
        return "permanent"
    if re.search(r"\b429\b|quota|rate.?limit|resource_exhausted|payment required|depleted your monthly included credits", text):
        return "quota"
    if re.search(r"\b(?:408|500|502|503|504)\b|timeout|timed out|temporarily unavailable|connection", text):
        return "transient"
    return "other"


def _should_disable_provider(message: str) -> bool:
    return bool(re.search(r"\b(?:401|403|404|408|429|500|502|503|504)\b", str(message or "")))


def _provider_timeout(name: str, remaining: float) -> float:
    for prefix, limit in _PROVIDER_TIMEOUTS.items():
        if name.startswith(prefix):
            return max(0.1, min(remaining, limit))
    return max(0.1, min(remaining, 4.0))


def _disable(name: str, reason: str) -> None:
    family = _provider_family(name)
    _DISABLED.add(name)
    if reason in {"permanent", "quota"}:
        _DISABLED_FAMILIES.add(family)
    print(f"[Light Router] disabled={name} family={family} reason={reason}", flush=True)


def call_llm_with_fallback(system_prompt, user_content, providers=None):
    providers = providers or get_quality_chain()
    last = None
    deadline = time.monotonic() + _ROUTER_BUDGET_SECONDS
    transient_retries = {}
    for name, fn in providers:
        family = _provider_family(name)
        if name in _DISABLED or family in _DISABLED_FAMILIES:
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        timeout = _provider_timeout(name, remaining)
        future = _CALL_EXECUTOR.submit(fn, system_prompt, user_content)
        try:
            result = future.result(timeout=timeout)
            if result:
                print(f"[Light Router] success={name}", flush=True)
                return result, name
        except concurrent.futures.TimeoutError:
            last = TimeoutError(f"{name}: exceeded provider timeout of {timeout:.1f}s")
            _disable(name, "transient")
        except QuotaExceeded as exc:
            last = exc
            _disable(name, _failure_class(str(exc)))
        except Exception as exc:
            last = exc
            reason = _failure_class(str(exc))
            print(f"[Light Router] error={name} reason={reason} | {exc}", flush=True)
            if reason in {"permanent", "quota"}:
                _disable(name, reason)
            elif reason == "transient" and transient_retries.get(family, 0) < _MAX_TRANSIENT_RETRIES:
                transient_retries[family] = transient_retries.get(family, 0) + 1
                retry_future = _CALL_EXECUTOR.submit(fn, system_prompt, user_content)
                try:
                    retry_result = retry_future.result(timeout=min(timeout, max(0.1, deadline - time.monotonic())))
                    if retry_result:
                        print(f"[Light Router] success={name} retry={transient_retries[family]}", flush=True)
                        return retry_result, name
                except Exception as retry_exc:
                    last = retry_exc
                    _disable(name, _failure_class(str(retry_exc)))
            else:
                _disable(name, reason)
        if deadline - time.monotonic() <= 0:
            break
    print(f"[Light Router] exhausted; last={last}", flush=True)
    return None, None
