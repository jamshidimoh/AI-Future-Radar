from pathlib import Path

import yaml

from src.editorial_quality_policy import BODY_PERSIAN_RATIO_MIN, TITLE_PERSIAN_RATIO_MIN
from src.unified_editorial_selection import load_editorial_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "production_contract.yaml"
MISSION = ROOT / "config" / "mission_policy.yaml"
SELECTION = ROOT / "config" / "selection_policy.yaml"
SOURCES = ROOT / "config" / "sources.yaml"
ARCHITECTURE = ROOT / "ARCHITECTURE.md"


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_production_contract_is_explicit_and_versioned():
    data = _load(CONTRACT)
    assert data["contract"]["version"] == 2
    assert data["contract"]["mission_policy"] == "config/mission_policy.yaml"
    assert data["contract"]["selection_policy"] == "config/selection_policy.yaml"
    assert data["contract"]["architecture_document"] == "ARCHITECTURE.md"


def test_protected_leader_and_source_contract_matches_current_configuration():
    contract = _load(CONTRACT)
    mission = _load(MISSION)
    sources = _load(SOURCES)

    protected = contract["protected"]
    assert protected["people"]["distinct_per_run"] is True
    assert protected["people"]["max_slots"] == 2
    source_names = {x["name"] for x in protected["sources"]}
    mission_names = {x["name"] for x in mission.get("protected_sources", [])}
    preferred_names = {x["name"] for x in sources.get("action_policy", {}).get("preferred_authoritative_sources", [])}
    assert "MIT CSAIL - Building 32" in source_names
    assert source_names <= mission_names
    assert source_names <= preferred_names


def test_mission_and_selection_layers_resolve_to_one_executable_contract():
    contract = load_editorial_contract()
    selection = _load(SELECTION)["selection"]
    mission = _load(MISSION)["mission"]
    assert contract["max_posts"] == selection["max_posts"] == mission["max_posts"]
    assert contract["candidate_window"] == 6
    assert contract["replacement_buffer"] == 2
    assert contract["preferred_max_same_source"] == mission["max_same_source"] == 1
    assert contract["hard_max_same_source"] == selection["max_items_per_source"] == 2
    assert contract["min_unique_sources"] == mission["min_unique_sources"]
    assert contract["min_authoritative_items"] == mission["min_authoritative_items"]
    assert contract["community_max"] == mission["community_max"]
    assert selection["diversity_mode"] == "adaptive"
    assert selection["diverse_sources_first"] if "diverse_sources_first" in selection else selection["distinct_sources_first"]


def test_mission_targets_are_not_allowed_to_drift():
    contract = _load(CONTRACT)["mission"]
    mission = _load(MISSION)["mission"]
    assert set(contract["required_areas"]) == {
        "ai_core", "convergence", "mind_cognition", "future_governance"
    }
    assert contract["min_unique_sources"] == mission["min_unique_sources"]
    assert contract["preferred_max_same_source_per_run"] == mission["max_same_source"]
    assert contract["hard_max_same_source_per_run"] == _load(SELECTION)["selection"]["max_items_per_source"]
    assert contract["min_authoritative_items"] == mission["min_authoritative_items"]
    assert contract["community_max"] == mission["community_max"]
    assert contract["ai_core_target"] == [
        mission["ai_core_target_min"], mission["ai_core_target_max"]
    ]
    assert contract["convergence_target"] == mission["convergence_target"]
    assert contract["mind_future_target"] == mission["mind_future_target"]
    assert contract["research_target"] == mission["research_target"]
    assert contract["interview_target_max"] == mission["interview_target_max"]


def test_quality_contract_matches_editorial_quality_gate():
    quality = _load(CONTRACT)["quality"]
    assert quality["title_persian_ratio_min"] == TITLE_PERSIAN_RATIO_MIN
    assert quality["body_persian_ratio_min"] == BODY_PERSIAN_RATIO_MIN
    assert quality["generic_why_blocked"] is True
    assert quality["source_evidence_required"] is True
    assert quality["adaptive_normal_score_policy"] is True


def test_source_boundary_and_architecture_are_synced():
    contract = _load(CONTRACT)
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for domain in contract["source_boundary"]["excluded_domains"]:
        assert domain in text
    assert "production_contract.yaml" in text
    assert "Protected sources" in text
    assert "priority candidates" in text
    assert "replacement" in text.lower()
