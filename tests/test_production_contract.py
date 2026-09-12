    source_names = {
        str(item.get("source") or item.get("source_name") or "")
        for item in _load(MISSION)["sources"]
    }
    preferred_names = set(selection_policy()["preferred_sources"])
    mission_names = set(_load(MISSION)["preferred_sources"])
    assert source_names <= mission_names
    assert source_names <= preferred_names


def test_mission_and_selection_layers_resolve_to_one_executable_contract():
    contract = load_editorial_contract()
    selection = _load(SELECTION)["selection"]
    mission = _load(MISSION)["mission"]
    assert contract["max_posts"] == selection["max_posts"] == 3
    assert mission["max_posts"] >= contract["max_posts"]
    assert contract["candidate_window"] == 6
    assert contract["replacement_buffer"] == 3
    assert contract["preferred_max_same_source"] == mission["max_same_source"] == 1
    assert contract["hard_max_same_source"] == selection["max_items_per_source"] == 2
    assert contract["min_unique_sources"] == mission["min_unique_sources"]
    assert contract["min_authoritative_items"] == mission["min_authoritative_items"]
    assert contract["community_max"] == mission["community_max"]
    assert selection["diversity_mode"] == "adaptive"
    assert selection["distinct_sources_first"] is True


def test_mission_diversity_is_explicit_and_canonical():
    contract = _load(CONTRACT)["mission"]
    mission = _load(MISSION)["mission"]
    assert set(contract["supported_areas"]) == {
        "ai_core", "convergence", "mind_cognition", "future_governance"
    }
    assert set(contract["supported_content_types"]) == set(mission["supported_content_types"])
