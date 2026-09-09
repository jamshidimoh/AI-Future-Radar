"""Isolated LiteLLM routing pilot for AI Future Radar.

This module is intentionally not wired into production yet. It proves that the
current Radar provider credentials can be represented as LiteLLM deployments
while keeping Radar's quality/ranking policy outside the infrastructure layer.
"""
from __future__ import annotations

import os
from typing import Any


PILOT_GROUP = "radar-pilot"


def _env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def build_model_list() -> list[dict[str, Any]]:
    """Build only credentialed pilot deployments; never expose key values."""
    rows: list[dict[str, Any]] = []

    if _env("OPENROUTER_API_KEY"):
        rows.append({
            "model_name": PILOT_GROUP,
            "litellm_params": {
                "model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
                "api_key": os.environ["OPENROUTER_API_KEY"],
                "timeout": 8,
                "order": 1,
            },
            "model_info": {"id": "openrouter-nemotron-3-super"},
        })

    if _env("GROQ_API_KEY"):
        for order, model, ident in (
            (2, "openai/gpt-oss-120b", "groq-gpt-oss-120b"),
            (3, "qwen/qwen3.6-27b", "groq-qwen3.6-27b"),
            (4, "openai/gpt-oss-20b", "groq-gpt-oss-20b"),
        ):
            rows.append({
                "model_name": PILOT_GROUP,
                "litellm_params": {
                    "model": f"groq/{model}",
                    "api_key": os.environ["GROQ_API_KEY"],
                    "timeout": 8,
                    "order": order,
                },
                "model_info": {"id": ident},
            })

    if _env("KIRAAI_API_KEY"):
        rows.append({
            "model_name": PILOT_GROUP,
            "litellm_params": {
                "model": "openai/minimax-m3-free",
                "api_key": os.environ["KIRAAI_API_KEY"],
                "api_base": "https://kiraai.vn/api/v1",
                "timeout": 8,
                "order": 5,
            },
            "model_info": {"id": "kiraai-minimax-m3-free"},
        })

    return rows


def build_router():
    """Create a LiteLLM Router with deployment-level failover."""
    try:
        from litellm import Router
    except ImportError as exc:  # pragma: no cover - exercised by environment
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
    """Call the pilot group and return content plus selected model/deployment."""
    response = router.completion(
        model=PILOT_GROUP,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    selected = str(getattr(response, "model", "unknown"))
    return content, selected
