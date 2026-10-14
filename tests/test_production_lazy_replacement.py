"""Integration regressions for provider-failure isolation and late QA replacement.

These tests run the production candidate loop with mocked discovery and delivery
boundaries. They do not contact providers, mutate persisted state, or send Telegram
messages.
"""
from __future__ import annotations

import main
from src.delivery_contract import delivered, policy_blocked
from src.llm_router_light import QuotaExceeded


def _install_isolated_runtime(monkeypatch, candidates, *, selected_count, delivery):
    """Make main.main deterministic while retaining the real production queue."""
    records = [dict(item) for item in candidates]

    monkeypatch.setattr(main, "configure_logging", lambda: None)
    monkeypatch.setattr(main, "fetch_rss_items", lambda *args, **kwargs: [dict(x) for x in records])
    monkeypatch.setattr(main, "fetch_youtube_items", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "fetch_google_news_items", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "load_seen", lambda: (set(), set()))
    monkeypatch.setattr(main, "load_source_history", lambda: {})
    monkeypatch.setattr(main, "save_seen", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "reconcile_people_bootstrap_state", lambda *args, **kwargs: {
        "status": "complete",
        "bootstrap_at": "2026-10-01T00:00:00+00:00",
    })
    monkeypatch.setattr(main, "_annotate_named_leader_interviews", lambda items, *args, **kwargs: list(items))
    monkeypatch.setattr(main, "post_bootstrap_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "deduplicate_people_signals", lambda items, **kwargs: list(items))
    monkeypatch.setattr(main, "filter_new_items", lambda items, _seen: list(items))
    monkeypatch.setattr(main, "_split_protected", lambda items, max_protected: ([], list(items)))
    monkeypatch.setattr(main, "filter_ai_relevance", lambda items, *args, **kwargs: list(items))
    monkeypatch.setattr(main, "enrich_items", lambda items, *args, **kwargs: list(items))
    monkeypatch.setattr(main, "enrich_signal_items", lambda items: list(items))
    monkeypatch.setattr(main, "_apply_signal_ranking", lambda items: None)
    monkeypatch.setattr(
        main,
        "gate_story_candidates",
        lambda _protected, leaders, regular, *_args, **_kwargs: list(leaders) + list(regular),
    )
    monkeypatch.setattr(
        main,
        "_refill_after_late_dedup",
        lambda selected, *_args, **_kwargs: list(selected),
    )
    monkeypatch.setattr(
        main,
        "_publication_summary_budget",
        lambda selected, *_args, **_kwargs: list(selected),
    )
    monkeypatch.setattr(main, "_voice_lane_recovery", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "_mission_coverage_recovery", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "resolve_source_image", lambda _item: "")
    monkeypatch.setattr(main, "_runtime_telemetry_event", lambda *args, **kwargs: None)

    def select(items, **_kwargs):
        return list(items)[:selected_count]

    def summarize(item):
        return {
            "summary": f"خلاصه تأییدشده برای {item['title']}",
            "why_it_matters": "اهمیت مستقل و قابل بررسی",
        }

    def format_post(item, *_args, **_kwargs):
        return (
            f"<b>📡 {item['title']}</b>\n"
            f"<blockquote>📌 <b>خلاصه</b>\n{item.get('summary', '')}</blockquote>"
        )

    hooks = {
        "select_editorial": select,
        "summarize_item": summarize,
        "format_post": format_post,
        "resolve_source_image": lambda _item: "",
        "send_to_telegram_safe": delivery,
        "persist_item_success": lambda *args, **kwargs: None,
    }
    return hooks


def _candidate(title: str, rank: int, score: float) -> dict:
    return {
        "title": title,
        "id": title,
        "source": f"source-{rank}",
        "source_name": f"source-{rank}",
        "source_type": "news",
        "source_tier": 1,
        "content_type": "news",
        "link": f"https://example.test/{rank}",
        "url": f"https://example.test/{rank}",
        "published": f"2026-10-{rank:02d}",
        "editorial_score": score,
        "final_editorial_score": score,
        "signal_score": 0,
        "normal_period_rank": rank,
    }


def test_late_publication_qa_rejection_sends_eligible_ranked_replacement(monkeypatch, capsys):
    first = _candidate("primary candidate rejected by final QA", 1, 90.0)
    replacement = _candidate("eligible ranked replacement", 2, 80.0)
    attempts = []

    def deliver(post, **_kwargs):
        attempts.append(post)
        if len(attempts) == 1:
            return policy_blocked("deterministic_final_qa_rejection")
        return delivered({"message_id": 702})

    hooks = _install_isolated_runtime(
        monkeypatch, [first, replacement], selected_count=1, delivery=deliver
    )
    main.main(hooks=hooks)
    output = capsys.readouterr().out

    assert len(attempts) == 2
    assert "primary candidate rejected by final QA" in attempts[0]
    assert "eligible ranked replacement" in attempts[1]
    assert "[Publication Lazy Refill] prepared replacement=1/" in output
    assert "Posts sent: 1/2" in output


def test_provider_failure_for_one_summary_does_not_abort_other_publication(monkeypatch, capsys):
    failed = _candidate("candidate with provider failure", 1, 90.0)
    healthy = _candidate("independent candidate still publishable", 2, 80.0)
    delivered_posts = []

    def summarize(item):
        if item["title"] == failed["title"]:
            raise QuotaExceeded("synthetic 429 for deterministic regression test")
        return {
            "summary": f"خلاصه تأییدشده برای {item['title']}",
            "why_it_matters": "اهمیت مستقل و قابل بررسی",
        }

    def deliver(post, **_kwargs):
        delivered_posts.append(post)
        return delivered({"message_id": 703})

    hooks = _install_isolated_runtime(
        monkeypatch, [failed, healthy], selected_count=2, delivery=deliver
    )
    hooks["summarize_item"] = summarize
    main.main(hooks=hooks)
    output = capsys.readouterr().out

    assert len(delivered_posts) == 1
    assert "independent candidate still publishable" in delivered_posts[0]
    assert "candidate with provider failure" not in delivered_posts[0]
    assert "[Editorial Gate] provider failure isolated candidate=" in output
    assert "Posts sent: 1/2" in output


def test_final_publication_ranking_rebuilds_ranks_after_summary_rejections():
    blocked = {
        "title": "rejected summary",
        "_publication_blocked": True,
        "period_rank": 1,
        "publication_rank_assigned": True,
        "normal_period_rank": 1,
    }
    first = {"title": "normal candidate one"}
    mind = {"title": "mind candidate", "mind_lane_selected": True}
    second = {"title": "normal candidate two"}
    education = {"title": "education", "content_type": "education"}
    queue = [blocked, first, mind, second, education]

    main._assign_final_publication_ranks(queue)

    assert "period_rank" not in blocked
    assert first["period_rank"] == 1
    assert first["normal_period_rank"] == 1
    assert mind["period_rank"] == 2
    assert mind["normal_period_rank"] is None
    assert second["period_rank"] == 3
    assert second["normal_period_rank"] == 2
    assert "period_rank" not in education


def test_late_replacement_rank_uses_open_slots_and_respects_window():
    queue = [
        {"period_rank": 1, "normal_period_rank": 1},
        {"period_rank": 2, "normal_period_rank": 2},
    ]
    assert main._next_lazy_normal_rank(queue, 0, 3) == 3
    assert main._next_lazy_normal_rank(queue, 0, 2) is None
    assert main._next_lazy_normal_rank([], 0, 3) == 1
