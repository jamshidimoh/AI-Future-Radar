import threading
import time

import pytest

import scripts.production_with_ranking_audit as launcher
from main import _summarize_selected
from src.llm_router_light import QuotaExceeded


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


def test_production_selector_delegates_to_canonical_period_rank(monkeypatch):
    selected = [{"title": "Tier-0 interview", "period_rank": 1}]
    captured = {}

    def rank(items, max_posts, max_per_source, max_per_type, policy):
        captured["args"] = (items, max_posts, max_per_source, max_per_type, policy)
        return selected

    monkeypatch.setattr(launcher, "_original_rank", rank)

    result = launcher._production_select([{"title": "candidate"}], 4, 2, 2, {"rotation_days": 7})

    assert result == selected
    assert captured["args"][1:] == (4, 2, 2, {"rotation_days": 7})


def test_parallel_summary_preserves_input_order_and_runs_concurrently(monkeypatch):
    monkeypatch.setenv("RADAR_SUMMARY_WORKERS", "2")
    state = {"active": 0, "peak": 0}
    lock = threading.Lock()

    def summarize(item):
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        time.sleep(0.05)
        with lock:
            state["active"] -= 1
        return {"title": f"done-{item['title']}"}

    items = [{"title": "a"}, {"title": "b"}, {"title": "c"}, {"title": "d"}]
    results = _summarize_selected(items, summarize)

    assert [result["title"] for result in results] == ["done-a", "done-b", "done-c", "done-d"]
    assert state["peak"] == 2


def test_summary_provider_failure_isolated_and_next_candidates_continue():
    calls = []

    def summarize(item):
        calls.append(item["title"])
        if item["title"] == "broken":
            raise QuotaExceeded("provider quota exhausted")
        return {"title": f"done-{item['title']}"}

    items = [{"title": "broken"}, {"title": "healthy"}]
    results = _summarize_selected(items, summarize)

    assert results == [None, {"title": "done-healthy"}]
    assert items[0]["_publication_blocked"] is True
    assert items[0]["_summary_provider_failure"] == "QuotaExceeded"
    assert calls == ["broken", "healthy"]


def test_summary_request_failure_isolated_without_swallowing_unexpected_errors():
    requests = pytest.importorskip("requests")

    def summarize(item):
        if item["title"] == "request-failed":
            raise requests.exceptions.Timeout("provider timed out")
        if item["title"] == "code-bug":
            raise ValueError("unexpected implementation error")
        return {"title": f"done-{item['title']}"}

    items = [{"title": "request-failed"}, {"title": "healthy"}]
    results = _summarize_selected(items, summarize)

    assert results == [None, {"title": "done-healthy"}]
    assert items[0]["_publication_blocked"] is True

    with pytest.raises(ValueError, match="unexpected implementation error"):
        _summarize_selected([{ "title": "code-bug" }], summarize)
