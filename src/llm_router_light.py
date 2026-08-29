"""Low-token, provider-diverse LLM router for production summarization.

The router is deliberately conservative: one provider-family failure should not
consume the budget on sibling models, while transient failures get a bounded
chance to recover. Model defaults favor currently supported endpoints and keep
fallback diversity explicit.
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
_PROVIDER_TIMEOUTS = {"Groq:": 6.0, "OpenRouter:": 4.0, "Gemini": 8.0}
_REQUEST_TIMEOUT = 8
_ROUTER_BUDGET_SECONDS = 14
_MAX_TRANSIENT_RETRIES = 1

# Qwen3.6-27B is currently supported on Groq; Qwen3.8-27B is newer but is not
# forced here because the production failure observed was account-wide 429s.
GROQ_MODELS = ("qwen/qwen3.6-27b", "openai/gpt-oss-120b")
# Use named, stable free OpenRouter endpoints instead of arbitrary discovery.
OPENROUTER_MODELS = ("openai/gpt-oss-120b:free", "openai/gpt-oss-20b:free")
GEMINI_DEFAULT_MODEL = "gemini-3.7-flash"


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
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 900,
        "stream": False,
    }
    if model.startswith("qwen/"):
        payload.update({"reasoning_effort": "none", "reasoning_format": "hidden", "temperature": 0.15})
    elif model.startswith("openai/gpt-oss"):
        payload.update({"reasoning_effort": "low", "temperature": 0.15})
    else:
        payload.update({"temperature": 0.15})
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=_REQUEST_TIMEOUT,
    )
    if r.status_code in (401, 402, 429):
        raise QuotaExceeded(f"Groq {model}: HTTP {r.status_code}")
    r.raise_for_status()
    return _extract_message(r.json())


def _openrouter(system_prompt, user_content, model):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 900,
            "temperature": 0.15,
        },
        timeout=_REQUEST_TIMEOUT,
    )
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
        response = client.models.generate_content(
            model=model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.15,
                max_output_tokens=900,
            ),
        )
        return response.text
    except Exception as exc:
        msg = str(exc).lower()
        if any(token in msg for token in ("401", "403", "404", "429", "quota", "resource_exhausted", "unauthenticated")):
            raise QuotaExceeded(f"Gemini {model}: {exc}") from exc
        raise


def get_quality_chain():
    global _CHAIN_CACHE
    if _CHAIN_CACHE is not None:
        return list(_CHAIN_CACHE)
    chain = []
    for model in GROQ_MODELS:
        chain.append((f"Groq:{model}", lambda sp, uc, m=model: _groq(sp, uc, m)))
    chain.append(("Gemini", _gemini))
    for model in OPENROUTER_MODELS:
        chain.append((f"OpenRouter:{model}", lambda sp, uc, m=model: _openrouter(sp, uc, m)))
    _CHAIN_CACHE = list(chain)
    print("[Light Router] chain=" + ", ".join(name for name, _ in chain), flush=True)
    return list(_CHAIN_CACHE)


def _failure_class(message: str) -> str:
    text = str(message or "").lower()
    if re.search(r"\b(?:401|403|404|unauthenticated|authentication|invalid.*credential|invalid.*key)\b", text):
        return "permanent"
    if re.search(r"\b429\b|quota|rate.?limit|resource_exhausted", text):
        return "quota"
    if re.search(r"\b(?:408|500|502|503|504)\b|timeout|timed out|temporarily unavailable|connection", text):
        return "transient"
    return "other"


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
            reason = _failure_class(str(exc))
            _disable(name, reason)
        except Exception as exc:
            last = exc
            reason = _failure_class(str(exc))
            print(f"[Light Router] error={name} reason={reason} | {exc}", flush=True)
            if reason in {"permanent", "quota"}:
                _disable(name, reason)
            elif reason == "transient" and transient_retries.get(family, 0) < _MAX_TRANSIENT_RETRIES:
                transient_retries[family] = transient_retries.get(family, 0) + 1
                print(f"[Light Router] transient retry family={family} retry={transient_retries[family]}", flush=True)
                retry_future = _CALL_EXECUTOR.submit(fn, system_prompt, user_content)
                try:
                    retry_result = retry_future.result(timeout=min(timeout, max(0.1, deadline - time.monotonic())))
                    if retry_result:
                        print(f"[Light Router] success={name} retry={transient_retries[family]}", flush=True)
                        return retry_result, name
                except Exception as retry_exc:
                    last = retry_exc
                    retry_reason = _failure_class(str(retry_exc))
                    print(f"[Light Router] retry failed={name} reason={retry_reason} | {retry_exc}", flush=True)
                    _disable(name, retry_reason)
            else:
                _disable(name, "other")
        if deadline - time.monotonic() <= 0:
            break

    print(f"[Light Router] exhausted; last={last}", flush=True)
    return None, None
