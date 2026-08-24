import scripts.production_with_ranking_audit as launcher


def test_audited_main_wraps_existing_selection_hook(monkeypatch):
    captured = {}
    audited = []

    def select(items, max_posts, max_per_source, max_per_type, policy):
        return [{"period_rank": 1, "title": "top story"}]

    def fake_main(hooks=None):
        captured["hooks"] = hooks
        result = hooks["select_editorial"]([], 4, 2, 2, {})
        captured["result"] = result
        return 0

    monkeypatch.setattr(launcher, "_original_main", fake_main)
    monkeypatch.setattr(launcher, "audit_selection", lambda items: audited.append(list(items)))

    assert launcher._audited_main({"select_editorial": select}) == 0
    assert captured["result"] == [{"period_rank": 1, "title": "top story"}]
    assert audited == [[{"period_rank": 1, "title": "top story"}]]


def test_production_selector_retains_tier0_interview_and_normal_portfolio(monkeypatch):
    tier0 = {
        "title": "Leader interview",
        "_rank_is_tier0": True,
        "protected_content": True,
        "leader": "Leader",
        "final_editorial_score": 40,
    }
    normal = {
        "title": "Normal AI story",
        "_rank_is_tier0": False,
        "protected_content": False,
        "final_editorial_score": 80,
    }

    monkeypatch.setattr(launcher.pipeline, "_exclude_published_candidates", lambda items: list(items))
    monkeypatch.setattr(launcher.pipeline, "_prepare_rank_features", lambda items: items)
    monkeypatch.setattr(launcher.pipeline, "_priority_story_diversified", lambda items: list(items))
    monkeypatch.setattr(launcher, "select_normal_portfolio", lambda *args, **kwargs: [normal])

    selected = launcher._production_select([tier0, normal], 4, 2, 2, {})

    assert selected == [tier0, normal]
    assert tier0["tier0_rank"] == 1
    assert tier0["normal_period_rank"] is None
    assert tier0["period_rank"] == 1
    assert normal["tier0_rank"] is None
    assert normal["normal_period_rank"] == 1
    assert normal["period_rank"] == 2
