"""Controlled bridge for introducing intelligence outputs safely.

The bridge is side-effect free by construction: it creates an auditable
proposal and only permits an integration decision when mode and gates are
explicitly satisfied. It never sends messages or mutates publication state.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = 1
ALLOWED_MODES = {"off", "shadow", "controlled"}


def _stable_id(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"bridge-g8-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def validate_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(policy)
    mode = str(result.get("mode") or "off")
    if mode not in ALLOWED_MODES:
        raise ValueError("unsupported integration mode")
    if not isinstance(result.get("apply"), bool):
        raise ValueError("apply must be boolean")
    if mode != "controlled" and result["apply"]:
        raise ValueError("apply may only be true in controlled mode")
    if result.get("rollback_enabled") is not True:
        raise ValueError("rollback_enabled must be true")
    return result


def build_controlled_proposal(
    *,
    candidate: Mapping[str, Any],
    baseline: Mapping[str, Any],
    policy: Mapping[str, Any],
    shadow_passed: bool,
) -> dict[str, Any]:
    cfg = validate_policy(policy)
    candidate_id = str(candidate.get("scenario_set_id") or candidate.get("proposal_id") or "")
    if not candidate_id:
        raise ValueError("candidate requires a stable scenario/proposal identity")
    baseline_id = str(baseline.get("run_id") or baseline.get("window_digest") or "")
    if not baseline_id:
        raise ValueError("baseline requires run_id or window_digest")

    gate_reasons = []
    if not shadow_passed:
        gate_reasons.append("shadow_measurement_failed")
    if cfg["mode"] == "off":
        gate_reasons.append("integration_off")
    if cfg["mode"] == "shadow":
        gate_reasons.append("shadow_only")
    if cfg["mode"] == "controlled" and not cfg["apply"]:
        gate_reasons.append("controlled_apply_disabled")

    allowed = not gate_reasons
    return {
        "schema_version": SCHEMA_VERSION,
        "proposal_id": _stable_id({"candidate": candidate_id, "baseline": baseline_id}),
        "candidate_id": candidate_id,
        "baseline_id": baseline_id,
        "mode": cfg["mode"],
        "shadow_passed": bool(shadow_passed),
        "rollback_enabled": True,
        "allowed_to_apply": allowed,
        "gate_reasons": gate_reasons,
        "publication_side_effect": False,
    }


def validate_proposal(proposal: Mapping[str, Any]) -> dict[str, Any]:
    if int(proposal.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("unsupported bridge schema_version")
    if proposal.get("publication_side_effect") is not False:
        raise ValueError("bridge must remain publication side-effect free")
    if proposal.get("rollback_enabled") is not True:
        raise ValueError("rollback must remain enabled")
    if not isinstance(proposal.get("gate_reasons"), list):
        raise ValueError("gate_reasons must be a list")
    return json.loads(json.dumps(proposal, ensure_ascii=False, sort_keys=True))
