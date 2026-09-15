from main import _mission_coverage_recovery


def _disable_history_dedup(monkeypatch):
    monkeypatch.setattr("main.filter_new_items", lambda items, _seen: list(items))


def _legacy_recovery_contract(monkeypatch):
    from src import unified_editorial_selection
    contract = unified_editorial_selection.load_editorial_contract()
    contract["ai_core_target_min"] = 0
    contract["convergence_target"] = 0
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 1
    monkeypatch.setattr(unified_editorial_selection, "load_editorial_contract", lambda: dict(contract))


def test_mission_coverage_recovery_targets_exact_mind_lane(monkeypatch):
    _disable_history_dedup(monkeypatch)
    selected = [
        {"title": "AI core", "mission_area": "ai_core", "link": "https://example.invalid/ai", "editorial_score": 90},
        {"title": "Convergence", "mission_area": "convergence", "link": "https://example.invalid/conv", "editorial_score": 90},
    ]
    wrong = {
        "title": "Wrong governance lane",
        "mission_area": "future_governance",
        "link": "https://example.invalid/wrong",
        "source": "NIST",
        "source_tier": 1,
        "editorial_score": 100,
    }
    right = {
        "title": "Right consciousness lane",
        "mission_area": "mind_cognition",
        "link": "https://example.invalid/right",
        "source": "Nature",
        "source_tier": 1,
        "editorial_score": 90,
    }

    def select_fn(items, **_kwargs):
        return [items[0]]

    recovered = _mission_coverage_recovery(
        selected,
        selected + [wrong, right],
        select_fn,
        lambda item: {"summary": f"Valid summary for {item['title']}"},
        2,
        2,
        {},
        set(),
    )
    assert len(recovered) == 1
    item, summary = recovered[0]
    assert item["mission_area"] == "mind_cognition"
    assert item["_mission_recovery"] is True
    assert summary["summary"].startswith("Valid summary")


def test_mission_coverage_recovery_replaces_failed_legacy_future_candidate(monkeypatch):
    _disable_history_dedup(monkeypatch)
    _legacy_recovery_contract(monkeypatch)
    failed = {
        "title": "Failed first",
        "mission_area": "future_governance",
        "link": "https://example.invalid/failed-first",
        "_publication_blocked": True,
    }
    rejected = {
        "title": "Still weak",
        "mission_area": "future_governance",
        "link": "https://example.invalid/rejected",
        "source": "Nature",
        "source_tier": 1,
        "editorial_score": 90,
    }
    valid = {
        "title": "Good future policy",
        "mission_area": "future_governance",
        "link": "https://example.invalid/valid",
        "source": "Nature",
        "source_tier": 1,
        "editorial_score": 80,
    }

    def select_fn(items, **_kwargs):
        return [items[0]]

    calls = {"n": 0}

    def summarize_fn(item):
        calls["n"] += 1
        return None if item["title"] == "Still weak" else {"summary": "Valid"}

    recovered = _mission_coverage_recovery(
        [failed],
        [failed, rejected, valid],
        select_fn,
        summarize_fn,
        2,
        2,
        {},
        set(),
    )

    assert len(recovered) == 1
    assert recovered[0][0]["title"] == "Good future policy"
    assert calls["n"] == 2
