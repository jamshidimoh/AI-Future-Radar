"""Isolated LiteLLM routing pilot for AI Future Radar.

This module is intentionally not wired into production yet. It proves that the
Radar provider credentials can be represented as LiteLLM deployments while
keeping Radar's quality/ranking policy outside the infrastructure layer.
"""
from __future__ import annotations

import os
from typing import Any

PILOT_GROUP = "radar-pilot"


def _env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _append(rows: list[dict[str, Any]], order: int, model: str, ident: str, key_env: str, **extra: Any) -> None:
    key = _env(key_env)
    if not key:
        return
    params: dict[str, Any] = {"model": model, "api_key": key, "timeout": 8, "order": order}
    params.update(extra)
    rows.append({"model_name": PILOT_GROUP, "litellm_params": params, "model_info": {"id": ident}})


def build_model_list() -> list[dict[str, Any]]:
    """Build only credentialed pilot deployments; never expose key values."""
    rows: list[dict[str, Any]] = []
    _append(rows, 1, "openrouter/nvidia/nemotron-3-super-120b-a12b:free", "openrouter-nemotron-3-super", "OPENROUTER_API_KEY")
    if _env("GROQ_API_KEY"):
        for order, model, ident in (
            (2, "groq/openai/gpt-oss-120b", "groq-gpt-oss-120b"),
            (3, "groq/qwen/qwen3.6-27b", "groq-qwen3.6-27b"),
            (4, "groq/openai/gpt-oss-20b", "groq-gpt-oss-20b"),
        ):
            _append(rows, order, model, ident, "GROQ_API_KEY")
    _append(rows, 5, "openai/minimax-m3-free", "kiraai-minimax-m3-free", "KIRAAI_API_KEY", api_base="https://kiraai.vn/api/v1")
    _append(rows, 6, "gemini/gemini-3-flash-preview", "gemini-3-flash-preview", "GEMINI_API_KEY")
    _append(rows, 7, "cerebras/glm-4.7", "cerebras-glm-4.7", "CEREBRAS_API_KEY")
    return rows


def build_router():
    """Create a LiteLLM Router with deployment-level failover."""
    try:
        from litellm import Router
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("LiteLLM is not installed") from exc
    model_list = build_model_list()
    if not model_list:
        raise RuntimeError("No credentialed pilot deployment is available")
    return Router(
        model_list=model_list,
        num_retries=0,
        retry_after=0,
        timeout=8,
        allowed_fails=1,
        cooldown_time=45,
        enable_pre_call_checks=True,
        fallbacks=[],
    )


def smoke_call(router, prompt: str = "Return JSON with one key named ok and value true.") -> tuple[str, str]:
    response = router.completion(
        model=PILOT_GROUP,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    selected = str(getattr(response, "model", "unknown"))
    return content, selected
