from src.unified_editorial_selection import is_mission_relevant


def test_generic_ai_story_is_rejected_in_strict_mode_without_link():
    item = {"title": "A new model update", "category": ""}
    assert not is_mission_relevant(item, strict=True)


def test_explicit_ai_link_allows_protected_story():
    item = {"title": "Leader interview", "_ai_link": True}
    assert is_mission_relevant(item, strict=True)


def test_specific_mission_category_is_relevant():
    item = {"title": "Quantum computing milestone", "category": "quantum"}
    assert is_mission_relevant(item, strict=True)
