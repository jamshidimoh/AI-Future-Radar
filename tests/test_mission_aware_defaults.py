from __future__ import annotations

import main
import period_ranked_pipeline


def test_main_editorial_default_is_mission_aware():
    captured = {}

    def fake_select(*args, **kwargs):
        captured.update(kwargs)
        return []

    original = main.select_regular_portfolio
    try:
        main.select_regular_portfolio = fake_select
        main._select_editorial_default(
            [], max_posts=1, max_per_source=1, max_per_type=1, policy={}
        )
    finally:
        main.select_regular_portfolio = original

    assert captured["mission_aware"] is True


def test_period_ranked_pipeline_uses_same_mission_aware_default(monkeypatch):
    captured = {}

    def fake_select(*args, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(period_ranked_pipeline, "select_regular_portfolio", fake_select)
    period_ranked_pipeline._diversify_normal_candidates(
        [], max_posts=1, max_per_source=1, max_per_type=1, policy={}
    )
    assert captured["mission_aware"] is True


def test_main_strict_relevance_default_is_false():
    captured = {}

    def fake_select(*args, **kwargs):
        captured.update(kwargs)
        return []

    original = main.select_regular_portfolio
    try:
        main.select_regular_portfolio = fake_select
        main._select_editorial_default(
            [], max_posts=1, max_per_source=1, max_per_type=1, policy={}
        )
    finally:
        main.select_regular_portfolio = original

    assert captured["strict_relevance"] is False


def test_period_ranked_pipeline_strict_relevance_default_is_false(monkeypatch):
    captured = {}

    def fake_select(*args, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(period_ranked_pipeline, "select_regular_portfolio", fake_select)
    period_ranked_pipeline._diversify_normal_candidates(
        [], max_posts=1, max_per_source=1, max_per_type=1, policy={}
    )
    assert captured["strict_relevance"] is False
