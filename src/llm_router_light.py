"""Production LLM router with deterministic registry-driven failover."""
from __future__ import annotations

import concurrent.futures
import logging
import os
import re
import sys
import threading
import time

import requests

logger = logging.getLogger(__name__)

_CALL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-call")

class QuotaExceeded(Exception):
    """Provider-side quota, auth, permission, or availability failure."""

_DISABLED: set[str] = set()
_DISABLED_FAMILIES: set[str] = set()
_MODEL_DISABLED_UNTIL: dict[str, float] = {}
_MODEL_DISABLED_REASON: dict[str, str] = {}
_STATE_LOCK = threading.RLock()
_CHAIN_CACHE = None
_CHAIN_CACHE_KEY = None
_PRODUCTION_POLICY_APPLIED = False
_PRODUCTION_CIRCUIT_BREAKER_INSTALLED = False
_PRODUCTION_CIRCUIT_OPEN = False
_OLLAMA_CIRCUIT_OPEN = False
_LITELLM_ROUTER = None
_LITELLM_ROUTER_KEY = None
_PROVIDER_TIMEOUTS = {"Groq:": 8.0, "NaraRouter:": 8.0, "OpenRouter:": 7.0, "KiraAI:": 8.0, "Gemini": 8.0, "HuggingFace": 5.0}
_REQUEST_TIMEOUT = 10
_ROUTER_BUDGET_SECONDS = float(os.getenv("RADAR_ROUTER_BUDGET_SECONDS", "10") or 10)
_MAX_TRANSIENT_RETRIES = 1
_MODEL_COOLDOWN_SECONDS = {"quota": 12.0, "model": 45.0, "transient": 10.0, "other": 15.0}
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"
NARA_DEFAULT_MODEL = "auto/bynara"

class ProductionQualityChain(list):
    """Marker type for the registry-produced production chain."""

def _provider_family(name: str) -> str:
    return str(name or "").split(":", 1)[0].strip().casefold()

def _provider_credential_available(name: str) -> bool:
    env = {"groq":"GROQ_API_KEY","nararouter":"NARAROUTER_API_KEY","openrouter":"OPENROUTER_API_KEY","kiraai":"KIRAAI_API_KEY","gemini":"GEMINI_API_KEY","huggingface":"HF_TOKEN"}.get(_provider_family(name))
    return bool(os.getenv(env)) if env else False

def _extract_message(payload: dict):
    choices = payload.get("choices") or []
    if not choices: raise QuotaExceeded("LLM response has no choices")
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") or {}
    if isinstance(message, dict) and message.get("content") is not None: return message["content"]
    if choice.get("text") is not None: return choice["text"]
    raise QuotaExceeded("LLM response content not found")

def _groq(system_prompt, user_content, model, *, output_mode="native"):
    key = os.getenv("GROQ_API_KEY")
    if not key: return None
    payload = {"model":model,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],"max_completion_tokens":850,"stream":False,"temperature":0.15}
    if output_mode == "native": payload["response_format"] = {"type":"json_object"}
    if model.startswith("qwen/"): payload.update({"reasoning_effort":"none","reasoning_format":"hidden"})
    elif model.startswith("openai/gpt-oss"): payload["reasoning_effort"] = "low"
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=payload,timeout=_REQUEST_TIMEOUT)
    if r.status_code in (401,402,403,404,429): raise QuotaExceeded(f"Groq {model}: HTTP {r.status_code} {r.text[:400]}")
    r.raise_for_status(); return _extract_message(r.json())

def _nara(system_prompt, user_content, model=None):
    key = os.getenv("NARAROUTER_API_KEY")
    if not key: return None
    selected_model = (model or os.getenv("NARA_MODEL") or NARA_DEFAULT_MODEL).strip()
    payload = {"model":selected_model,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],"max_tokens":900,"temperature":0.15}
    r = requests.post("https://router.bynara.id/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=payload,timeout=8)
    if r.status_code in (401,402,403,404,429,503): raise QuotaExceeded(f"NaraRouter {selected_model}: HTTP {r.status_code} {r.text[:800]}")
    r.raise_for_status(); return _extract_message(r.json())

def _openrouter_supports_response_format(model: str) -> bool:
    from src.free_model_registry import model_capability
    return bool(model_capability(model).get("response_format"))

def _openrouter(system_prompt, user_content, model, *, output_mode="native"):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key: return None
    payload = {"model":model,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],"max_tokens":850,"temperature":0.15}
    if output_mode == "native" and _openrouter_supports_response_format(model): payload["response_format"]={"type":"json_object"}
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","HTTP-Referer":"https://github.com/jamshidimoh/AI-Future-Radar","X-Title":"AI Future Radar"},json=payload,timeout=_REQUEST_TIMEOUT)
    if r.status_code in (401,403,404,429): raise QuotaExceeded(f"OpenRouter {model}: HTTP {r.status_code} {r.text[:800]}")
    if r.status_code == 402: raise QuotaExceeded(f"OpenRouter {model}: HTTP 402 account_limit {r.text[:800]}")
    r.raise_for_status(); return _extract_message(r.json())

OLLAMA_FREE_DEFAULT_MODEL = "qwen3:1.7b"
OLLAMA_FREE_MODELS = {"qwen3:1.7b"}

def _ollama_local(system_prompt, user_content):
    """Zero-cost local emergency provider using Ollama; no API key or billing dependency."""
    global _OLLAMA_CIRCUIT_OPEN
    if _OLLAMA_CIRCUIT_OPEN:
        raise QuotaExceeded("OllamaLocal circuit open for current production run")
    model = (os.getenv("RADAR_OLLAMA_FREE_MODEL") or OLLAMA_FREE_DEFAULT_MODEL).strip()
    if model not in OLLAMA_FREE_MODELS:
        raise QuotaExceeded(f"OllamaLocal rejected non-audited model={model}")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.10},
    }
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=float(os.getenv("RADAR_OLLAMA_TIMEOUT_SECONDS", "20")),
        )
        if response.status_code in (404, 429, 500, 503):
            raise QuotaExceeded(
                f"OllamaLocal {model}: HTTP {response.status_code} {response.text[:800]}"
            )
        response.raise_for_status()
        data = response.json()
        content = (data.get("message") or {}).get("content")
        if not content:
            raise QuotaExceeded(f"OllamaLocal {model}: response has no content")
        return content
    except QuotaExceeded:
        raise
    except (requests.RequestException, ValueError) as exc:
        raise QuotaExceeded(f"OllamaLocal {model}: {type(exc).__name__}: {exc}") from exc

def _gemini(system_prompt, user_content):
    key = os.getenv("GEMINI_API_KEY")
    if not key: return None
    from google import genai
    from google.genai import types
    model = (os.getenv("GEMINI_MODEL") or GEMINI_DEFAULT_MODEL).strip()
    client = genai.Client(api_key=key,http_options={"timeout":8000})
    try:
        response = client.models.generate_content(model=model,contents=user_content,config=types.GenerateContentConfig(system_instruction=system_prompt,response_mime_type="application/json",max_output_tokens=850))
        return response.text
    except Exception as exc:
        logger.warning("Gemini provider attempt failed provider=gemini model=%s exception=%s: %s", model, type(exc).__name__, exc, exc_info=True)
        raise QuotaExceeded(f"Gemini {model}: {exc}") from exc

def _hf_price_is_free(item):
    if item.get("free") is True: return True
    p=item.get("pricing") or {}
    try: return float(p.get("input",-1)) == 0 and float(p.get("output",-1)) == 0
    except (TypeError,ValueError): return False

def _discover_hf_models():
    try:
        token=os.getenv("HF_TOKEN"); headers={"Authorization":f"Bearer {token}"} if token else {}
        r=requests.get("https://router.huggingface.co/v1/models",headers=headers,timeout=10)
        if r.status_code in (401,403): raise QuotaExceeded(f"HF discovery unauthorized: HTTP {r.status_code}")
        r.raise_for_status(); payload=r.json(); rows=payload.get("data",payload if isinstance(payload,list) else [])
        return [x for x in rows if isinstance(x,dict) and x.get("id")]
    except QuotaExceeded: raise
    except Exception as exc:
        logger.warning("Hugging Face model discovery failed: %s", exc, exc_info=True)
        return []

def _select_hf_model(models=None):
    rows=list(models) if isinstance(models,list) else _discover_hf_models(); free=[m for m in rows if isinstance(m,dict) and _hf_price_is_free(m)]
    explicit=(os.getenv("HF_MODEL") or "").strip()
    if explicit and any(m.get("id")==explicit for m in free): return explicit
    if not free: raise QuotaExceeded("No zero-price Hugging Face chat model is currently available")
    preferred=[m for m in free if "qwen" in str(m.get("id","")).lower()]
    return str((preferred or free)[0].get("id"))

def _huggingface(system_prompt,user_content):
    token=os.getenv("HF_TOKEN")
    if not token: return None
    from huggingface_hub import InferenceClient
    model=_select_hf_model(); response=InferenceClient(token=token,provider="auto").chat.completions.create(model=model,messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],max_tokens=850)
    return response.choices[0].message.content

def _chain_key():
    return tuple(os.getenv(x,"") for x in ("GROQ_API_KEY","NARAROUTER_API_KEY","OPENROUTER_API_KEY","KIRAAI_API_KEY","GEMINI_API_KEY","HF_TOKEN")) + (os.getenv("RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK","0"),os.getenv("RADAR_ENABLE_OPENROUTER_FREE_ROUTER","0"),os.getenv("RADAR_ENABLE_GEMINI_FALLBACK","0"),os.getenv("RADAR_ENABLE_HF_FALLBACK","0"),os.getenv("RADAR_OLLAMA_FREE_MODEL",OLLAMA_FREE_DEFAULT_MODEL),os.getenv("GEMINI_MODEL",GEMINI_DEFAULT_MODEL),os.getenv("NARA_MODEL",NARA_DEFAULT_MODEL))

def get_quality_chain():
    global _CHAIN_CACHE,_CHAIN_CACHE_KEY
    key=_chain_key()
    if _CHAIN_CACHE is not None and key == _CHAIN_CACHE_KEY: return ProductionQualityChain(_CHAIN_CACHE)
    from src.free_model_registry import build_production_chain
    chain=build_production_chain(sys.modules[__name__]); _CHAIN_CACHE=list(chain); _CHAIN_CACHE_KEY=key
    print("[Light Router] chain="+", ".join(n for n,_ in chain),flush=True); return ProductionQualityChain(_CHAIN_CACHE)

def _litellm_model_list():
    from src.free_model_registry import build_litellm_model_list
    return build_litellm_model_list()

def _get_litellm_router():
    global _LITELLM_ROUTER,_LITELLM_ROUTER_KEY
    if os.getenv("RADAR_USE_LITELLM","1").strip().lower() in {"0","false","no","off"}: return None
    model_list=_litellm_model_list()
    if not model_list: return None
    key=tuple((x["model_info"]["id"],x["litellm_params"]["model"]) for x in model_list)
    if _LITELLM_ROUTER is not None and key == _LITELLM_ROUTER_KEY: return _LITELLM_ROUTER
    try:
        from litellm import Router
        _LITELLM_ROUTER=Router(model_list=model_list,num_retries=0,retry_after=0,timeout=8,allowed_fails=1,cooldown_time=45,enable_pre_call_checks=True,fallbacks=[]); _LITELLM_ROUTER_KEY=key
        print("[LiteLLM Router] deployments="+", ".join(x["model_info"]["id"] for x in model_list),flush=True); return _LITELLM_ROUTER
    except Exception as exc:
        logger.error("LiteLLM router initialization failed provider=litellm model=%s exception=%s", ",".join(x["model_info"]["id"] for x in model_list), type(exc).__name__, exc_info=True)
        print(f"[LiteLLM Router] initialization_failed={type(exc).__name__}: {exc}",flush=True); return None

def _nara_response_adapter(system_prompt,user_content,deployment_id,*,max_tokens=700,timeout=8):
    model=deployment_id.split(":",1)[1] if ":" in deployment_id else NARA_DEFAULT_MODEL; key=os.getenv("NARAROUTER_API_KEY")
    if not key: raise QuotaExceeded("NaraRouter missing credential")
    payload={"model":model,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],"max_tokens":max_tokens,"temperature":0.15}
    response=requests.post("https://router.bynara.id/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=payload,timeout=timeout)
    if response.status_code in (401,402,403,404,429,503): raise QuotaExceeded(f"NaraRouter {model}: HTTP {response.status_code} {response.text[:500]}")
    response.raise_for_status(); data=response.json(); content=_extract_message(data)
    class Message: pass
    class Choice: pass
    class Response: pass
    out=Response(); out.model=data.get("model",model); msg=Message(); msg.content=content; choice=Choice(); choice.message=msg; out.choices=[choice]; return out

def _call_direct_deployment(litellm_router,deployment,system_prompt,user_content,*,max_tokens=700,timeout=8):
    deployment_id=str(deployment.get("model_info",{}).get("id") or "")
    if _provider_family(deployment_id)=="nararouter": return _nara_response_adapter(system_prompt,user_content,deployment_id,max_tokens=max_tokens,timeout=timeout)
    kwargs={"model":deployment["model_name"],"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],"timeout":timeout,"max_tokens":max_tokens,"temperature":0.15}
    use_json_mode = bool(deployment.get("model_info",{}).get("response_format"))
    if use_json_mode:
        kwargs["response_format"]={"type": "json_object"}
    # Groq GPT-OSS exposes reasoning separately. Explicitly suppress it so
    # LiteLLM reliably receives the final assistant content for editorial JSON.
    if _provider_family(deployment_id) == "groq" and "/gpt-oss-" in deployment_id.lower():
        kwargs["include_reasoning"] = False
    try:
        return litellm_router.completion(**kwargs)
    except Exception as exc:
        # Groq GPT-OSS currently rejects otherwise-valid JSON-mode requests with
        # json_validate_failed on some editorial prompts. The summarizer already
        # has a strict JSON extractor, so retry once without provider-side JSON mode.
        if use_json_mode and _provider_family(deployment_id) == "groq" and "json_validate_failed" in str(exc).lower() and "/gpt-oss-" in deployment_id.lower():
            kwargs.pop("response_format", None)
            print(f"[Groq JSON Recovery] response_format_disabled deployment={deployment_id}", flush=True)
            return litellm_router.completion(**kwargs)
        raise

def _failure_class(message:str)->str:
    text=str(message or "").lower()
    if "401" in text or "unauthorized" in text or "invalid api" in text or "authentication" in text: return "auth"
    if "no deployments available" in text or "router exhausted" in text or "production llm circuit exhausted" in text: return "transient"
    if "429" in text or "rate limit" in text or "too many requests" in text: return "quota"
    if "timeout" in text or "timed out" in text: return "transient"
    if "403" in text or "404" in text or "not found" in text: return "model"
    return "other"

def _provider_quota_is_family_scoped(family:str,reason:str,message:str)->bool:
    if reason=="auth": return True
    return reason=="quota" and family in {"openrouter","nararouter","kiraai"} and re.search(r"\b402\b|account_limit|requests?/day|daily|free.*tier|balance|wallet|vnd",message,re.I) is not None

def _model_is_disabled(name:str)->bool:
    with _STATE_LOCK: until=_MODEL_DISABLED_UNTIL.get(name,0.0)
    return until>time.monotonic()

def _disable(name:str,reason:str):
    with _STATE_LOCK:
        _DISABLED.add(name)
        _MODEL_DISABLED_UNTIL[name] = time.monotonic() + _MODEL_COOLDOWN_SECONDS.get(reason, _MODEL_COOLDOWN_SECONDS["other"])
        _MODEL_DISABLED_REASON[name] = reason



def reset_recoverable_cooldowns() -> int:
    """Clear only transient/quota model cooldowns before mission recovery retries.
    
    Persistent provider health, authentication failures, and model-not-found
    failures remain protected. This only reopens models whose last failure is
    reasonably retryable within the current production run.
    """
    cleared = 0
    with _STATE_LOCK:
        for name, reason in list(_MODEL_DISABLED_REASON.items()):
            if reason not in {"quota", "transient"}:
                continue
            _DISABLED.discard(name)
            _MODEL_DISABLED_UNTIL.pop(name, None)
            _MODEL_DISABLED_REASON.pop(name, None)
            cleared += 1
    if cleared:
        print(f"[Recovery Router] reset_recoverable_cooldowns={cleared}", flush=True)
    return cleared

def _should_disable_provider(message:str)->bool:
    return re.search(r"\b401\b|unauthorized|authentication failed|invalid api|\b403\b|\b404\b|\b503\b",str(message or "").lower()) is not None

def _litellm_router_disabled()->bool:
    with _STATE_LOCK: return bool(_DISABLED_FAMILIES)

def _call_litellm(system_prompt,user_content):
    global _PRODUCTION_CIRCUIT_OPEN
    if _PRODUCTION_CIRCUIT_OPEN:
        print("[Production Circuit] open=true reason=prior_provider_exhaustion", flush=True)
        return None,None
    router=_get_litellm_router()
    if router is None: return None,None
    model_list=_litellm_model_list(); deadline=time.monotonic()+_ROUTER_BUDGET_SECONDS
    local_models:set[str]=set(); local_families:set[str]=set(); last_error=None; availability_failures=0
    for deployment in model_list:
        deployment_id=str(deployment.get("model_info",{}).get("id") or ""); family=_provider_family(deployment_id)
        if deployment_id in local_models or family in local_families: continue
        if family in _DISABLED_FAMILIES or _model_is_disabled(deployment_id): continue
        remaining=deadline-time.monotonic()
        if remaining<=0: print("[LiteLLM Router] budget_exhausted=1",flush=True); break
        try:
            response=_call_direct_deployment(router,deployment,system_prompt,user_content,max_tokens=700,timeout=max(0.5,min(8.0,remaining)))
            content=getattr(response.choices[0].message,"content",None) if getattr(response,"choices",None) else None
            if not content: raise ValueError("LiteLLM response has no content")
            selected=str(getattr(response,"model",deployment_id)); print(f"[LiteLLM Router] success={deployment_id} model={selected}",flush=True); return content,deployment_id
        except Exception as exc:
            last_error=exc; message=str(exc); reason=_failure_class(message); local_models.add(deployment_id)
            logger.warning(
                "LiteLLM provider attempt failed provider=%s model=%s exception=%s: %s",
                family,
                deployment_id,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            print(
                f"[LiteLLM Router] failed={deployment_id}: exception={type(exc).__name__} "
                f"provider={family} model={deployment_id} {exc}",
                flush=True,
            )
            _disable(deployment_id,reason)
            if reason in {"auth", "quota", "transient", "model"}:
                availability_failures += 1
            if _provider_quota_is_family_scoped(family,reason,message):
                local_families.add(family)
                with _STATE_LOCK: _DISABLED_FAMILIES.add(family)
    if last_error is not None:
        print(f"[LiteLLM Router] exhausted={type(last_error).__name__}: {last_error}",flush=True)
        if availability_failures > 0 or "no deployments available" in str(last_error).lower():
            _PRODUCTION_CIRCUIT_OPEN = True
            print(
                f"[Production Circuit] open=true provider_exhaustion=1 availability_failures={availability_failures}",
                flush=True,
            )
    return None,None

def call_llm_with_fallback(system_prompt,user_content,providers=None):
    canonical_chain = providers is None or isinstance(providers,ProductionQualityChain)
    production_mode = os.getenv("RADAR_PRODUCTION_MODE", "0").strip().lower() in {"1", "true", "yes"}
    if canonical_chain and production_mode and _PRODUCTION_CIRCUIT_BREAKER_INSTALLED and _PRODUCTION_CIRCUIT_OPEN and _OLLAMA_CIRCUIT_OPEN:
        raise QuotaExceeded("Production LLM circuit open: remote providers and local fallback exhausted")
    if canonical_chain and production_mode and _PRODUCTION_CIRCUIT_BREAKER_INSTALLED:
        result, provider = _call_litellm(system_prompt, user_content)
        if result:
            print(f"[Production Router Bridge] success={provider}", flush=True)
            return result, provider
        # The local Ollama runner is installed and smoke-tested by the production
        # workflow, but historically it was only available to the non-LiteLLM
        # path. That left the production circuit without a zero-cost emergency
        # provider exactly when the remote providers were exhausted.
        if os.getenv("RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK", "0").strip().lower() in {"1", "true", "yes"} and not _OLLAMA_CIRCUIT_OPEN:
            try:
                local_result = _ollama_local(system_prompt, user_content)
                if local_result:
                    print("[Production Router Bridge] success=OllamaLocal:qwen3:1.7b emergency_fallback=true", flush=True)
                    return local_result, "OllamaLocal:qwen3:1.7b"
            except Exception as exc:
                global _OLLAMA_CIRCUIT_OPEN
                _OLLAMA_CIRCUIT_OPEN = True
                logger.warning("Local Ollama emergency fallback failed: %s", exc, exc_info=True)
                print(f"[Production Router Bridge] OllamaLocal failed={type(exc).__name__}: {exc}; circuit_open=true", flush=True)
        raise QuotaExceeded("Production LLM circuit exhausted without usable provider response")
    if canonical_chain:
        providers=get_quality_chain()
    deadline=time.monotonic()+_ROUTER_BUDGET_SECONDS; local_models:set[str]=set(); local_families:set[str]=set(); last_error=None
    for name,fn in providers:
        family=_provider_family(name)
        if name in local_models or family in local_families or family in _DISABLED_FAMILIES or _model_is_disabled(name) or not _provider_credential_available(name): continue
        remaining=deadline-time.monotonic()
        if remaining<=0: break
        future=_CALL_EXECUTOR.submit(fn,system_prompt,user_content)
        try:
            result=future.result(timeout=_provider_timeout(name,remaining))
            if result: print(f"[Light Router] success={name}",flush=True); return result,name
        except concurrent.futures.TimeoutError:
            last_error=TimeoutError(f"{name}: provider timeout"); local_models.add(name); _disable(name,"transient")
            logger.warning(
                "Provider attempt timed out provider=%s model=%s exception=TimeoutError",
                family,
                name,
                exc_info=True,
            )
        except QuotaExceeded as exc:
            last_error=exc; reason=_failure_class(str(exc)); local_models.add(name)
            logger.warning(
                "Provider quota attempt failed provider=%s model=%s exception=%s: %s",
                family,
                name,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            if _provider_quota_is_family_scoped(family,reason,str(exc)):
                local_families.add(family)
                with _STATE_LOCK: _DISABLED_FAMILIES.add(family)
            _disable(name,reason)
        except Exception as exc:
            last_error=exc; local_models.add(name); _disable(name,_failure_class(str(exc)))
            logger.warning(
                "Provider attempt failed provider=%s model=%s exception=%s: %s",
                family,
                name,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
        finally:
            if future.done(): future.cancel()
    if last_error is not None: raise last_error
    return None,None

def _provider_timeout(name:str,remaining:float)->float:
    for prefix,limit in _PROVIDER_TIMEOUTS.items():
        if name.startswith(prefix): return max(0.1,min(remaining,limit))
    return max(0.1,min(remaining,4.0))
