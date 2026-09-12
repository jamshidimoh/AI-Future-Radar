from main import _mission_coverage_recovery


def test_mission_coverage_recovery_replaces_failed_mind_future_candidate(monkeypatch):
    monkeypatch.setenv("RADAR_SUMMARY_WORKERS", "1")
    failed = {
        "title": "Harari item",
        "mission_area": "future_governance",
        "link": "https://example.invalid/failed",
        "_publication_blocked": True,
    }
    replacement = {
        "title": "Consciousness research",
        "mission_area": "mind_cognition",
        "link": "https://example.invalid/replacement",
        "source": "Nature",
        "source_tier": 1,
        "editorial_score": 90,
    }

    def select_fn(items, **_kwargs):
        return [items[0]]

    def summarize_fn(item):
        return {"summary": f"Valid summary for {item['title']}"}

    recovered = _mission_coverage_recovery(
        [failed],
        [failed, replacement],
        select_fn,
        summarize_fn,
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


def test_mission_coverage_recovery_does_not_bypass_quality_gate(monkeypatch):
    monkeypatch.setenv("RADAR_SUMMARY_WORKERS", "1")
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
