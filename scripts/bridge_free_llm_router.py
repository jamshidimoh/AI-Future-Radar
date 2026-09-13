"""Bridge Free LLM Router health discovery into the runtime OpenRouter registry.

Free LLM Router is a discovery/availability layer, not an inference provider.
This bridge promotes only concrete OpenRouter free model IDs that are usable
for the Radar's text/JSON workload. Health evidence controls resilience, not
intelligence rank.
"""
from __future__ import annotations

import argparse
import copy
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "artifacts" / "free_model_registry.runtime.yaml"
TIMEOUT = 12
MAX_CANDIDATES = 40
MIN_QUALITY = 50.0
MAX_QUALITY = 64.0
BLOCKED_IDS = {"openrouter/free", "openrouter/auto"}


def _get_json(url: str, *, token: str | None = None, query: dict | None = None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(url, headers=headers, params=query or {}, timeout=TIMEOUT)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, payload if isinstance(payload, dict) else {}


def _zero_price(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    try:
        return float(pricing.get("prompt", pricing.get("input", "-1"))) == 0 and float(pricing.get("completion", pricing.get("output", "-1"))) == 0
    except (TypeError, ValueError):
        return False


def _text_capable(model: dict) -> bool:
    architecture = model.get("architecture") or {}
    inputs = architecture.get("input_modalities") or ["text"]
    outputs = architecture.get("output_modalities") or ["text"]
    return "text" in inputs and "text" in outputs


def _load() -> dict:
    if not RUNTIME_PATH.exists():
        raise RuntimeError(f"Runtime registry not found: {RUNTIME_PATH}")
    value = yaml.safe_load(RUNTIME_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict) or not isinstance(value.get("runtime"), dict):
        raise RuntimeError("Invalid runtime registry")
    return value


def _candidate_quality(reliability: float, rank: int) -> float:
    reliability = max(0.0, min(100.0, reliability))
    rank_bonus = max(0.0, min(4.0, (MAX_CANDIDATES - rank) / 10.0))
    return round(min(MAX_QUALITY, max(MIN_QUALITY, 50.0 + reliability * 0.10 + rank_bonus)), 3)


def bridge() -> dict:
    data = _load()
    runtime = data["runtime"]
    flr_token = os.getenv("FREE_LLM_ROUTER_API_KEY", "").strip()
    or_token = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not flr_token or not or_token:
        runtime["flr_bridge"] = {"enabled": False, "reason": "missing credential"}
        runtime["discovery_candidates"] = [
            row for row in (runtime.get("discovery_candidates") or [])
            if isinstance(row, dict) and str(row.get("id") or "").strip().casefold() not in BLOCKED_IDS
        ]
        RUNTIME_PATH.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return data

    status, payload = _get_json(
        "https://freellmrouter.com/api/v1/models/full",
        token=flr_token,
        query={"useCase": "chat", "sort": "capable", "topN": MAX_CANDIDATES, "maxErrorRate": 40, "timeRange": "7d"},
    )
    if status >= 400:
        raise RuntimeError(f"Free LLM Router catalog failed HTTP {status}")

    flr_models = payload.get("models") or []
    if not isinstance(flr_models, list):
        flr_models = []
    feedback = payload.get("feedbackCounts") or {}
    if not isinstance(feedback, dict):
        feedback = {}

    status, or_payload = _get_json("https://openrouter.ai/api/v1/models", token=or_token)
    if status >= 400:
        raise RuntimeError(f"OpenRouter catalog failed HTTP {status}")
    or_models = {str(row.get("id")): row for row in (or_payload.get("data") or []) if isinstance(row, dict) and row.get("id")}

    registry = data.get("registry") or {}
    trusted_ids = {str(model.get("id")) for provider in registry.get("providers", []) or [] for model in provider.get("models", []) or []}
    existing = runtime.get("discovery_candidates") or []
    candidates = [
        row for row in existing
        if isinstance(row, dict) and str(row.get("id") or "").strip().casefold() not in BLOCKED_IDS
    ]
    existing_ids = {str(row.get("id")) for row in candidates}

    accepted = 0
    rejected = 0
    rejection_reasons: dict[str, int] = {}
    generated_at = str(runtime.get("generated_at") or datetime.now(timezone.utc).isoformat())

    for rank, flr_model in enumerate(flr_models, start=1):
        if not isinstance(flr_model, dict):
            continue
        model_id = str(flr_model.get("id") or "").strip()
        live = or_models.get(model_id)
        reasons: list[str] = []
        if not model_id:
            reasons.append("missing_id")
        if model_id.casefold() in BLOCKED_IDS:
            reasons.append("non_routable_alias")
        if model_id in trusted_ids:
            reasons.append("already_trusted")
        if model_id in existing_ids:
            reasons.append("already_discovered")
        if not live:
            reasons.append("not_in_openrouter_catalog")
        elif not _zero_price(live):
            reasons.append("not_free_now")
        if live and not _text_capable(live):
            reasons.append("not_text_io")

        if reasons:
            rejected += 1
            for reason in reasons:
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            continue

        health = feedback.get(model_id) or {}
        try:
            error_rate = float(health.get("errorRate", 0.0) or 0.0)
        except (TypeError, ValueError):
            error_rate = 0.0
        reliability = max(0.0, min(100.0, 100.0 - error_rate))
        quality = _candidate_quality(reliability, rank)
        row = {
            "id": model_id,
            "family": "openrouter",
            "free": True,
            "chat_capable": True,
            "json_capable": True,
            "response_format": "response_format" in {str(x).strip() for x in (live.get("supported_parameters") or [])},
            "context_length": int(live.get("context_length") or 0),
            "priority": 1200,
            "reliability_score": round(reliability, 3),
            "base_quality": 70.0,
            "task_fit": 70.0,
            "quality_score": quality,
            "quality_evidence": "free-llm-router-health-only",
            "promotion_status": "free-llm-router-health-qualified",
            "discovery_source": "free-llm-router",
            "flr_rank": rank,
            "flr_error_rate_7d": round(error_rate, 3),
            "flr_last_updated": str(payload.get("lastUpdated") or ""),
            "runtime_discovered_at": generated_at,
        }
        candidates.append(copy.deepcopy(row))
        existing_ids.add(model_id)
        accepted += 1

    candidates.sort(key=lambda row: (-float(row.get("quality_score", 0.0)), int(row.get("priority", 9999)), str(row.get("id", ""))))
    runtime["discovery_candidates"] = candidates[:MAX_CANDIDATES]
    runtime["flr_bridge"] = {
        "enabled": True,
        "source": "freellmrouter.com/api/v1/models/full",
        "use_case": "chat",
        "time_range": "7d",
        "max_error_rate": 40,
        "returned_models": len(flr_models),
        "accepted_models": accepted,
        "rejected_models": rejected,
        "rejection_reasons": rejection_reasons,
        "quality_policy": "health-only conservative score 50-64; never outranks benchmark-backed models",
    }
    RUNTIME_PATH.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(yaml.safe_dump(runtime["flr_bridge"], allow_unicode=True, sort_keys=False), flush=True)
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    data = bridge()
    if args.strict and data["runtime"].get("flr_bridge", {}).get("enabled") and data["runtime"].get("flr_bridge", {}).get("accepted_models", 0) == 0:
        raise SystemExit("FLR bridge validated successfully but produced zero eligible candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
