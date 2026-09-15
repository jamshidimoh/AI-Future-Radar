import src.priority_people as priority_people


def test_phi_is_not_a_raw_substring_match(monkeypatch):
    monkeypatch.setattr(priority_people, "_IDEA_CACHE", [{"name": "integrated_information", "mission_area": "mind_cognition", "ai_bridge_terms": ["phi"]}])
    item = {"title": "A philosophical discussion of battery materials", "content_type": "research"}
    priority_people.priority_people_features(item)
    assert item["priority_ideas"] == []


def test_integrated_information_theory_has_mind_sublane(monkeypatch):
    monkeypatch.setattr(priority_people, "_IDEA_CACHE", [{"name": "integrated_information", "mission_area": "mind_cognition", "ai_bridge_terms": ["integrated information theory"]}])
    item = {"title": "Integrated information theory and machine consciousness", "content_type": "research"}
    priority_people.priority_people_features(item)
    assert item["priority_ideas"] == ["integrated_information"]
    assert item["priority_idea_sublanes"] == ["human_mind"]


def test_ai_to_mind_direction_is_explicit(monkeypatch):
    monkeypatch.setattr(priority_people, "_IDEA_CACHE", [{"name": "consciousness", "mission_area": "mind_cognition", "ai_bridge_terms": ["machine consciousness"]}])
    item = {"title": "Sam Altman discusses machine consciousness", "content_type": "interview", "watch_person": "Sam Altman", "is_leader_watch": True}
    priority_people.priority_people_features(item)
    assert item["person_idea_direction"] == "ai_to_mind"


def test_mind_to_ai_direction_is_explicit(monkeypatch):
    monkeypatch.setattr(priority_people, "_IDEA_CACHE", [{"name": "future_of_mind", "mission_area": "future_governance", "ai_bridge_terms": ["human-AI convergence"]}])
    item = {"title": "Karl Friston on human-AI convergence", "content_type": "research", "watch_person": "Karl Friston", "is_leader_watch": True}
    priority_people.priority_people_features(item)
    assert item["person_idea_direction"] == "mind_to_ai"


def test_friston_is_mapped_to_mind_domain_in_pioneers():
    from pathlib import Path
    import yaml
    data = yaml.safe_load(Path("config/pioneers.yaml").read_text(encoding="utf-8"))
    row = next(x for x in data["people"] if x["name"] == "Karl Friston")
    assert row["category"] == "mind_consciousness"
