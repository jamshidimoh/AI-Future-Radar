from pathlib import Path

import yaml


def test_normal_selection_policy_allows_only_one_story_per_source():
    path = Path(__file__).resolve().parents[1] / "config" / "selection_policy.yaml"
    policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert policy["selection"]["max_items_per_source"] == 1


def test_source_diversity_policy_is_explicitly_documented():
    path = Path(__file__).resolve().parents[1] / "config" / "selection_policy.yaml"
    text = path.read_text(encoding="utf-8")
    assert "max_items_per_source=1" in text
