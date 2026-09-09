import main


def test_selection_refills_slot_removed_by_late_dedup(monkeypatch):
    selected = [{"title": "already published", "id": "old"}]
    pool = [
        {"title": "already published", "id": "old"},
        {"title": "fresh replacement", "id": "new"},
    ]

    calls = []

    def fake_filter(items, _seen):
        calls.append([x["id"] for x in items])
        return [x for x in items if x["id"] != "old"]

    def fake_select(items, max_posts, max_per_source, max_per_type, policy):
        calls.append([x["id"] for x in items])
        return list(items)[:max_posts]

    monkeypatch.setattr(main, "filter_new_items", fake_filter)

    result = main._refill_after_late_dedup(
        selected,
        pool,
        fake_select,
        max_posts=1,
        max_per_source=2,
        max_per_type=2,
        policy={},
        seen_hashes=set(),
        cap=1,
    )

    assert [x["id"] for x in result] == ["new"]
    assert calls


def test_selection_refill_never_reuses_protected_candidates(monkeypatch):
    selected = []
    pool = [
        {"title": "protected", "id": "protected", "protected_content": True},
        {"title": "fresh", "id": "fresh"},
    ]

    monkeypatch.setattr(main, "filter_new_items", lambda items, _seen: list(items))

    def fake_select(items, max_posts, max_per_source, max_per_type, policy):
        assert all(not x.get("protected_content") for x in items)
        return list(items)[:max_posts]

    result = main._refill_after_late_dedup(
        selected,
        pool,
        fake_select,
        max_posts=1,
        max_per_source=2,
        max_per_type=2,
        policy={},
        seen_hashes=set(),
        cap=1,
    )

    assert [x["id"] for x in result] == ["fresh"]
