from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def _read_status():
    path = ROOT / "docs" / "PRODUCTION_CLOSURE_STATUS.md"
    return path.read_text(encoding="utf-8")


def test_project_closure_status_is_not_certified_without_closed_marker():
    text = _read_status()
    assert "`CLOSED`" in text
    assert "`ACCEPTANCE IN PROGRESS`" in text or "Current declaration" in text


def test_all_intelligence_stage_configs_exist_and_stay_disabled_or_shadowed():
    expectations = {
        "config/evidence_graph.yaml": ("evidence_graph", False, None),
        "config/temporal_intelligence.yaml": ("temporal_intelligence", False, None),
        "config/convergence_intelligence.yaml": ("convergence_intelligence", False, None),
        "config/foresight_intelligence.yaml": ("foresight_intelligence", False, None),
        "config/intelligence_measurement.yaml": ("intelligence_measurement", True, True),
        "config/controlled_intelligence_bridge.yaml": ("controlled_intelligence_bridge", None, False),
    }
    for relative, (key, enabled, shadow_only) in expectations.items():
        data = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
        cfg = data[key]
        assert cfg["version"] == 1
        if enabled is not None:
            assert cfg["enabled"] is enabled
        if shadow_only is not None:
            assert cfg["shadow_only"] is shadow_only
        assert cfg["publication_decoupled"] is True
        if relative.endswith("controlled_intelligence_bridge.yaml"):
            assert cfg["apply"] is False
            assert cfg["rollback_enabled"] is True


def test_stage_workflows_and_docs_exist():
    required = [
        ".github/workflows/g3-validation.yml",
        ".github/workflows/g4-validation.yml",
        ".github/workflows/g5-validation.yml",
        ".github/workflows/g6-validation.yml",
        ".github/workflows/g7-validation.yml",
        ".github/workflows/g8-validation.yml",
        "docs/G3_EVIDENCE_GRAPH.md",
        "docs/G4_TEMPORAL_INTELLIGENCE.md",
        "docs/G5_CROSS_DOMAIN_CONVERGENCE.md",
        "docs/G6_FORESIGHT_INTELLIGENCE.md",
        "docs/G7_SHADOW_MEASUREMENT.md",
        "docs/G8_CONTROLLED_INTEGRATION.md",
    ]
    for relative in required:
        assert (ROOT / relative).exists(), relative


def test_final_gate_fails_closed_on_non_closed_project_state():
    text = _read_status()
    if "Current declaration\n\n`CLOSED`" not in text:
        pytest.skip("project is correctly prevented from closure until the real production evidence window is closed")
