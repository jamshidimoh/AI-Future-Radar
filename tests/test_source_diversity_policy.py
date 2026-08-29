from pathlib import Path

import yaml

import period_ranked_pipeline as pipeline


def test_normal_selection_policy_allows_only_one_story_per_source():
    path = Path(__file__).resolve().parents[1] / "config" / "selection_policy.yaml"
    policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert policy["selection"]["max_items_per_source"] == 1


def test_source_diversity_policy_is_explicitly_documented():
    path = Path(__file__).resolve().parents[1] / "config" / "selection_policy.yaml"
    text = path.read_text(encoding="utf-8")
    assert "max_items_per_source=1" in text


def test_selector_rejects_second_same_source_when_other_source_can_fill_slot(monkeypatch):
    monkeypatch.setattr(pipeline._pipeline, "load_source_history", lambda: [])
    candidates = [
        {"title": "OpenAI top", "final_editorial_score": 100, "source": "OpenAI", "content_type": "news"},
        {"title": "OpenAI second", "final_editorial_score": 99, "source": "OpenAI", "content_type": "news"},
        {"title": "MIT alternative", "final_editorial_score": 90, "source": "MIT CSAIL", "content_type": "news"},
    ]
    selected = pipeline._diversify_normal_candidates(
        candidates,
        max_posts=2,
        max_per_source=1,
        max_per_type=2,
        policy={},
    )
    assert [item["title"] for item in selected] == ["OpenAI top", "MIT alternative"]


def test_selector_keeps_single_source_when_no_alternative_exists(monkeypatch):
    monkeypatch.setattr(pipeline._pipeline, "load_source_history", lambda: [])
    candidates = [
        {"title": "OpenAI top", "final_editorial_score": 100, "source": "OpenAI", "content_type": "news"},
        {"title": "OpenAI second", "final_editorial_score": 99, "source": "OpenAI", "content_type": "news"},
    ]
    selected = pipeline._diversify_normal_candidates(
        candidates,
        max_posts=2,
        max_per_source=1,
        max_per_type=2,
        policy={},
    )
    assert [item["title"] for item in selected] == ["OpenAI top"]
