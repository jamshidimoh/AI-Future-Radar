"""Provider-agnostic LLM router with free-first multi-model fallback and Persian-aware quality priority."""
import os
import re
import time
import requests


class QuotaExceeded(Exception):
    pass


_DISABLED_PROVIDERS = set()

# Hard constraint: candidates must be free at the active provider.
# Ranking then favors: Persian/multilingual fit -> reasoning/quality -> recency -> structured output -> speed.
# Qwen is intentionally first because its published multilingual support explicitly includes Persian.
GROQ_FREE_MODELS = (
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
)

# Known Chinese-family free variants that should receive a quality/Persian-prioritization boost
# when OpenRouter currently exposes them as :free. The list is advisory; discovery remains dynamic.
CHINESE_FREE_PREFIXES = (
    "qwen/",
    "qwen3",
    "qwen3.",
    "z-ai/",
    "thudm/",
    "moonshotai/",
    "minimax/",
    "deepseek/",
)


def _call_gemini(system_prompt, user_content):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai
    from google.genai import types
    model_name = (os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            ),
        )
    except Exception as exc:
        message = str(exc).lower()
        if "429" in message or "quota" in message or "resource_exhausted" in message:
            raise QuotaExceeded(f"Gemini quota exceeded: {exc}") from exc
        raise
    return response.text


def _call_groq_model(system_prompt, user_content, model):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    if resp.status_code in (401, 402, 429):
        raise QuotaExceeded(f"Groq unavailable/quota exceeded ({model}) HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.json()["choices"]["message"]["content"]


_HF_MODEL_CACHE = None
_HF_MODEL_CACHE_TS = 0.0
_HF_MODEL_CACHE_TTL = 900
_OPENROUTER_CACHE = None
_OPENROUTER_CACHE_TS = 0.0
_OPENROUTER_CACHE_TTL = 900


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
        headers = {"Authorization": f"Bearer {os.environ.get('HF_TOKEN')}"} if os.environ.get("HF_TOKEN") else {}
        response = requests.get("https://router.huggingface.co/v1/models", headers=headers, timeout=20)
        if response.status_code in (401, 403):
            raise QuotaExceeded(f"HF discovery unauthorized: HTTP {response.status_code}")
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data", payload if isinstance(payload, list) else [])
        normalized = []
        for item in models if isinstance(models, list) else []:
            if not isinstance(item, dict) or not _hf_supported_as_chat(item):
                continue
            providers = item.get("providers") or item.get("inferenceProviderMapping") or []
            pricing = item.get("pricing") or {}
            normalized.append({
                "id": item.get("id"),
                "free": _hf_price_is_free(item),
                "input": _num(pricing.get("input"), 999999),
                "output": _num(pricing.get("output"), 999999),
                "providers": len(providers) if isinstance(providers, (list, dict)) else 0,
                "latency": _num(item.get("first_token_latency_ms"), 999999),
                "throughput": _num(item.get("throughput"), 0),
                "context": int(item.get("context_length") or 0),
                "structured": bool(item.get("supports_structured_output")),
            })
        _HF_MODEL_CACHE, _HF_MODEL_CACHE_TS = normalized, now
        print(f"[HF Router] models discovered: {len(normalized)}")
        return normalized
    except QuotaExceeded:
        raise
    except Exception as exc:
        _HF_MODEL_CACHE, _HF_MODEL_CACHE_TS = [], now
        print(f"[HF Router] discovery failed: {exc}")
        return []


def _select_hf_model():
    policy = (os.environ.get("HF_POLICY") or "free-first").strip().lower()
    explicit = (os.environ.get("HF_MODEL") or "").strip()
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
        pool.sort(key=lambda m: (
            not any(str(m["id"]).lower().startswith(p) for p in CHINESE_FREE_PREFIXES),
            -(m["providers"] or 0),
            -(m["throughput"] or 0),
            m["latency"],
            -(m["context"] or 0),
        ))
    else:
        pool = sorted(structured, key=lambda m: (not m["free"], -(m["providers"] or 0), m["latency"]))
    if not pool:
        raise QuotaExceeded("No Hugging Face chat model is available")
    selected = pool[0]
    print(f"[HF Router] selected: {selected['id']} | free={selected['free']}")
    return selected["id"]


def _call_huggingface(system_prompt, user_content):
    token = os.environ.get("HF_TOKEN")
    if not token:
        return None
    from huggingface_hub import InferenceClient
    model = _select_hf_model()
    try:
        client = InferenceClient(token=token, provider="auto")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
            response_format={"type": "json_object"},
            max_tokens=1800,
        )
    except Exception as exc:
        message = str(exc)
        if "402" in message or "Payment Required" in message or "depleted your monthly included credits" in message:
            raise QuotaExceeded(f"Hugging Face quota/credits exhausted: {exc}") from exc
        raise
    return response.choices[0].message.content


def _call_openrouter(system_prompt, user_content, model):
    token = os.environ.get("OPENROUTER_API_KEY")
    if not token:
        return None
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
            "response_format": {"type": "json_object"},
        },
        timeout=45,
    )
    if resp.status_code in (401, 402, 429):
        raise QuotaExceeded(f"OpenRouter unavailable/quota exceeded ({model}) HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _get_openrouter_free_models():
    global _OPENROUTER_CACHE, _OPENROUTER_CACHE_TS
    now = time.time()
    if _OPENROUTER_CACHE is not None and now - _OPENROUTER_CACHE_TS < _OPENROUTER_CACHE_TTL:
        return _OPENROUTER_CACHE
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        models = [m.get("id", "") for m in rows if m.get("id", "").endswith(":free")]

        def rank(mid):
            low = mid.lower()
            chinese = 0 if any(low.startswith(p) for p in CHINESE_FREE_PREFIXES) else 1
            qwen = 0 if low.startswith("qwen/") or low.startswith("qwen3") or "qwen" in low else 1
            reasoning = 0 if any(k in low for k in ("reason", "thinking", "instruct")) else 1
            size_match = re.search(r"(\d+)[bB](?:-|:|$)", mid)
            size = int(size_match.group(1)) if size_match else 0
            return (chinese, qwen, reasoning, -size)

        models = sorted(set(models), key=rank)
        limit = max(1, int(os.environ.get("OPENROUTER_FREE_MODEL_LIMIT", "12")))
        _OPENROUTER_CACHE = models[:limit]
        _OPENROUTER_CACHE_TS = now
        print(f"[OpenRouter] free models discovered: {len(models)} | candidates={len(_OPENROUTER_CACHE)}")
    except Exception as exc:
        print(f"[OpenRouter] discovery failed: {exc}")
        _OPENROUTER_CACHE = []
        _OPENROUTER_CACHE_TS = now
    return _OPENROUTER_CACHE


def _groq_models():
    configured = (os.environ.get("GROQ_FREE_MODELS") or "").strip()
    if configured:
        models = [x.strip() for x in configured.split(",") if x.strip()]
    else:
        models = list(GROQ_FREE_MODELS)
    return models


def get_quality_chain():
    chain = []

    # Tier 1: current free models with strong multilingual/Persian fit and reasoning quality.
    # Qwen3.6-27B is first because Qwen explicitly documents Persian in its multilingual family.
    for model in _groq_models():
        name = f"Groq:{model}"
        chain.append((name, lambda sp, uc, _m=model: _call_groq_model(sp, uc, _m)))

    # Tier 2: dynamically discovered current free models; Chinese families are ranked first.
    for model in _get_openrouter_free_models():
        chain.append((f"OpenRouter:{model}", lambda sp, uc, _m=model: _call_openrouter(sp, uc, _m)))

    # Tier 3: Gemini free tier.
    chain.append(("Gemini", _call_gemini))

    # Tier 4: HF only when the discovered endpoint is genuinely zero-price.
    chain.append(("HuggingFace", _call_huggingface))
    print(f"[LLM Router] chain ready: {', '.join(name for name, _ in chain)}")
    return chain


def call_llm_with_fallback(system_prompt, user_content, providers=None, max_retries_per_provider=1):
    providers = providers or get_quality_chain()
    last_error = None
    for name, fn in providers:
        if name in _DISABLED_PROVIDERS:
            continue
        for attempt in range(max_retries_per_provider):
            try:
                result = fn(system_prompt, user_content)
                if result is None:
                    break
                print(f"[LLM Router] success: {name}")
                return result, name
            except QuotaExceeded as exc:
                _DISABLED_PROVIDERS.add(name)
                print(f"[LLM Router] disabled for this run: {name} | {exc}")
                last_error = exc
                break
            except Exception as exc:
                print(f"[LLM Router] error in {name} (attempt {attempt + 1}): {exc}")
                last_error = exc
                time.sleep(1)
    print(f"[LLM Router] all active providers failed. last_error={last_error}")
    return None, None
