from pathlib import Path

import yaml

import period_ranked_pipeline as pipeline


def test_normal_selection_policy_uses_adaptive_two_item_source_ceiling():
    path = Path(__file__).resolve().parents[1] / "config" / "selection_policy.yaml"
    policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert policy["selection"]["max_items_per_source"] == 2
    assert policy["selection"]["preferred_max_same_source"] == 1
    assert policy["selection"]["distinct_sources_first"] is True


def test_source_diversity_policy_is_explicitly_documented():
    path = Path(__file__).resolve().parents[1] / "config" / "selection_policy.yaml"
    text = path.read_text(encoding="utf-8")
    assert "adaptive ceiling" in text
    assert "a second item is allowed only during adaptive" in text


def test_selector_prefers_distinct_sources_before_repeating_a_source(monkeypatch):
    monkeypatch.setattr(pipeline._pipeline, "load_source_history", lambda: [])
    candidates = [
        {"title": "OpenAI top", "final_editorial_score": 100, "source": "OpenAI", "content_type": "news"},
        {"title": "OpenAI second", "final_editorial_score": 99, "source": "OpenAI", "content_type": "news"},
        {"title": "MIT alternative", "final_editorial_score": 90, "source": "MIT CSAIL", "content_type": "news"},
        {"title": "Nature alternative", "final_editorial_score": 89, "source": "Nature", "content_type": "news"},
    ]
    selected = pipeline._diversify_normal_candidates(candidates, 4, 2, 4, policy={"mission_aware": False})
    assert [item["source"] for item in selected] == ["OpenAI", "MIT CSAIL", "Nature", "OpenAI"]


def test_selector_can_use_second_story_when_no_other_source_exists(monkeypatch):
    monkeypatch.setattr(pipeline._pipeline, "load_source_history", lambda: [])
    candidates = [
        {"title": "OpenAI top", "final_editorial_score": 100, "source": "OpenAI", "content_type": "news"},
        {"title": "OpenAI second", "final_editorial_score": 99, "source": "OpenAI", "content_type": "news"},
    ]
    selected = pipeline._diversify_normal_candidates(candidates, 2, 2, 2, policy={})
    assert [item["title"] for item in selected] == ["OpenAI top", "OpenAI second"]


def test_historical_source_usage_does_not_make_all_recent_sources_ineligible(monkeypatch):
    monkeypatch.setattr(pipeline._pipeline, "load_source_history", lambda: [
        {"source": "OpenAI", "content_type": "news", "ts": 9999999999},
        {"source": "MIT CSAIL", "content_type": "news", "ts": 9999999999},
    ])
    candidates = [
        {"title": "OpenAI top", "final_editorial_score": 100, "source": "OpenAI", "content_type": "news"},
        {"title": "MIT alternative", "final_editorial_score": 90, "source": "MIT CSAIL", "content_type": "news"},
        {"title": "Nature alternative", "final_editorial_score": 80, "source": "Nature", "content_type": "news"},
    ]
    selected = pipeline._diversify_normal_candidates(candidates, 3, 2, 3, policy={"mission_aware": False})
    assert {item["source"] for item in selected} == {"OpenAI", "MIT CSAIL", "Nature"}
