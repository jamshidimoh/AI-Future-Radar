import pytest

from src.controlled_intelligence_bridge_v1 import (
    build_controlled_proposal,
    validate_policy,
    validate_proposal,
)


def policy(mode="shadow", apply=False):
    return {"mode": mode, "apply": apply, "rollback_enabled": True}


def test_shadow_mode_never_allows_apply():
    result = build_controlled_proposal(
        candidate={"scenario_set_id": "scenario-1"},
        baseline={"run_id": "run-1"},
        policy=policy(),
        shadow_passed=True,
    )
    assert result["allowed_to_apply"] is False
    assert "shadow_only" in result["gate_reasons"]
    assert result["publication_side_effect"] is False


def test_controlled_mode_requires_shadow_pass():
    result = build_controlled_proposal(
        candidate={"scenario_set_id": "scenario-1"},
        baseline={"run_id": "run-1"},
        policy=policy("controlled", True),
        shadow_passed=False,
    )
    assert result["allowed_to_apply"] is False
    assert "shadow_measurement_failed" in result["gate_reasons"]


def test_controlled_mode_can_pass_all_gates_without_publication_side_effect():
    result = build_controlled_proposal(
        candidate={"scenario_set_id": "scenario-1"},
        baseline={"run_id": "run-1"},
        policy=policy("controlled", True),
        shadow_passed=True,
    )
    assert result["allowed_to_apply"] is True
    assert result["gate_reasons"] == []
    assert result["publication_side_effect"] is False


def test_invalid_policy_fails_closed():
    with pytest.raises(ValueError, match="unsupported integration mode"):
        validate_policy({"mode": "production", "apply": False, "rollback_enabled": True})


def test_apply_outside_controlled_fails_closed():
    with pytest.raises(ValueError, match="controlled mode"):
        validate_policy({"mode": "shadow", "apply": True, "rollback_enabled": True})


def test_rollback_is_mandatory():
    with pytest.raises(ValueError, match="rollback_enabled"):
        validate_policy({"mode": "controlled", "apply": False, "rollback_enabled": False})


def test_invalid_proposal_side_effect_fails_closed():
    with pytest.raises(ValueError, match="side-effect"):
        validate_proposal({
            "schema_version": 1,
            "publication_side_effect": True,
            "rollback_enabled": True,
            "gate_reasons": [],
        })
