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
