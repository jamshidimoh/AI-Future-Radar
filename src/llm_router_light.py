"""Low-token, free-first LLM router for production summarization.

The router is centralized and fail-fast. Provider health is learned during a
run, quota failures disable a provider, and the total budget is intentionally
short so one bad provider cannot delay publication of the whole period.
"""
from __future__ import annotations

import concurrent.futures
import os
import re
import time
import requests

_CALL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-call")

class QuotaExceeded(Exception):
    pass

_DISABLED = set()
_CHAIN_CACHE = None
_OPENROUTER_CACHE = {}
_PROVIDER_TIMEOUTS = {"Groq:": 6.0, "OpenRouter:": 2.5, "Gemini": 10.0}
_REQUEST_TIMEOUT = 8
_OPENROUTER_DISCOVERY_TIMEOUT = 3
_ROUTER_BUDGET_SECONDS = 14

GROQ_MODELS = ("qwen/qwen3.6-27b", "openai/gpt-oss-120b")
CHINESE_HINTS = ("qwen", "z-ai", "thudm", "moonshot", "deepseek", "minimax")

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
    payload={"model":model,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],"response_format":{"type":"json_object"},"max_completion_tokens":900,"stream":False}
    if model.startswith("qwen/"):
        payload.update({"reasoning_effort":"none","reasoning_format":"hidden","temperature":0.15})
    elif model.startswith("openai/gpt-oss"):
        payload.update({"reasoning_effort":"low","temperature":0.15})
    else:
        payload.update({"temperature":0.15})
    r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=payload,timeout=_REQUEST_TIMEOUT)
    if r.status_code in (401,402,429):
        raise QuotaExceeded(f"Groq {model}: HTTP {r.status_code}")
    r.raise_for_status()
    return _extract_message(r.json())

def _openrouter_models(limit=2):
    key=os.getenv("OPENROUTER_API_KEY")
    if not key:
        return []
    if limit in _OPENROUTER_CACHE:
        return list(_OPENROUTER_CACHE[limit])
    try:
        r=requests.get("https://openrouter.ai/api/v1/models",headers={"Authorization":f"Bearer {key}"},timeout=_OPENROUTER_DISCOVERY_TIMEOUT)
        r.raise_for_status()
        ids=[str(x.get("id") or "") for x in r.json().get("data",[]) if str(x.get("id") or "").endswith(":free")]
        def rank(mid):
            low=mid.lower(); chinese=0 if any(h in low for h in CHINESE_HINTS) else 1; qwen=0 if "qwen" in low else 1; reasoning=0 if any(k in low for k in ("reason","thinking","instruct")) else 1
            match=re.search(r"(\d+)[bB](?:-|:|$)",mid); size=int(match.group(1)) if match else 0
            return (chinese,qwen,reasoning,-size)
        result=sorted(set(ids),key=rank)[:limit]
        _OPENROUTER_CACHE[limit]=list(result)
        return result
    except Exception as exc:
        print(f"[Light Router] OpenRouter discovery failed: {exc}",flush=True)
        _OPENROUTER_CACHE[limit]=[]
        return []

def _openrouter(system_prompt,user_content,model):
    key=os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json={"model":model,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_content}],"response_format":{"type":"json_object"},"max_tokens":900,"temperature":0.15},timeout=_REQUEST_TIMEOUT)
    if r.status_code in (401,402,429):
        raise QuotaExceeded(f"OpenRouter {model}: HTTP {r.status_code}")
    r.raise_for_status()
    return _extract_message(r.json())

def _gemini(system_prompt,user_content):
    key=os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    from google import genai
    from google.genai import types
    model=(os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    client=genai.Client(api_key=key,http_options={"timeout":10_000})
    try:
        response=client.models.generate_content(model=model,contents=user_content,config=types.GenerateContentConfig(system_instruction=system_prompt,response_mime_type="application/json",temperature=0.15,max_output_tokens=900))
        return response.text
    except Exception as exc:
        msg=str(exc).lower()
        if "429" in msg or "quota" in msg or "resource_exhausted" in msg:
            raise QuotaExceeded(f"Gemini quota: {exc}") from exc
        raise

def get_quality_chain():
    global _CHAIN_CACHE
    if _CHAIN_CACHE is not None:
        return list(_CHAIN_CACHE)
    chain=[]
    for model in GROQ_MODELS:
        chain.append((f"Groq:{model}",lambda sp,uc,m=model:_groq(sp,uc,m)))
    # Keep one predictable free OpenRouter candidate after the two primary Groq
    # models. Gemini remains available as an explicit fallback, but is not
    # allowed to turn every candidate into a 10-second serial wait.
    chain.append(("Gemini",_gemini))
    for model in _openrouter_models(limit=2):
        chain.append((f"OpenRouter:{model}",lambda sp,uc,m=model:_openrouter(sp,uc,m)))
    _CHAIN_CACHE=list(chain)
    print("[Light Router] chain="+", ".join(name for name,_ in chain),flush=True)
    return list(_CHAIN_CACHE)

def _should_disable_provider(message:str)->bool:
    return bool(re.search(r"\b(?:401|403|404|408|429|500|502|503|504)\b",str(message or "")))

def _provider_timeout(name:str,remaining:float)->float:
    for prefix,limit in _PROVIDER_TIMEOUTS.items():
        if name.startswith(prefix):
            return max(0.1,min(remaining,limit))
    return max(0.1,min(remaining,4.0))

def call_llm_with_fallback(system_prompt,user_content,providers=None):
    providers=providers or get_quality_chain()
    last=None; deadline=time.monotonic()+_ROUTER_BUDGET_SECONDS
    for name,fn in providers:
        if name in _DISABLED:
            continue
        remaining=deadline-time.monotonic()
        if remaining<=0:
            break
        timeout=_provider_timeout(name,remaining)
        future=_CALL_EXECUTOR.submit(fn,system_prompt,user_content)
        try:
            result=future.result(timeout=timeout)
            if result:
                print(f"[Light Router] success={name}",flush=True)
                return result,name
        except concurrent.futures.TimeoutError:
            last=TimeoutError(f"{name}: exceeded provider timeout of {timeout:.1f}s"); _DISABLED.add(name)
            print(f"[Light Router] hard-timeout={name} | disabling for this run",flush=True)
        except QuotaExceeded as exc:
            last=exc; _DISABLED.add(name)
            print(f"[Light Router] disabled={name} | {exc}",flush=True)
        except Exception as exc:
            last=exc; message=str(exc)
            print(f"[Light Router] error={name} | {message}",flush=True)
            if _should_disable_provider(message):
                _DISABLED.add(name); print(f"[Light Router] disabled={name} | unavailable provider/model",flush=True)
        if deadline-time.monotonic()<=0:
            break
    print(f"[Light Router] exhausted; last={last}",flush=True)
    return None,None
