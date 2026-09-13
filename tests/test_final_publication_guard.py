import json
from pathlib import Path

import src.publication_guard as publication_guard

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _write_ledger(tmp_path, records):
    path = tmp_path / "telegram_feedback.json"
    path.write_text(json.dumps({"version": 2, "messages": {str(i): record for i, record in enumerate(records)}}, ensure_ascii=False), encoding="utf-8")
    publication_guard.LEDGER_PATH = path


def test_exact_title_is_hard_blocked(tmp_path):
    _write_ledger(tmp_path, [{"title": "Coursera با ۱۰۰ میلیون دلار از طرح بازآموزی هوش مصنوعی Andrew Ng حمایت می‌کند", "link": "https://example.com/old"}])
    text = "<b>📡 Coursera با ۱۰۰ میلیون دلار از طرح بازآموزی هوش مصنوعی Andrew Ng حمایت می‌کند</b>\n"
    allowed, reason = publication_guard.check_before_publish(text, "https://example.com/new")
    assert not allowed
    assert reason == "exact_story_title_already_published"


def test_canonical_url_is_hard_blocked_even_when_title_changes(tmp_path):
    _write_ledger(tmp_path, [{"title": "Old headline", "link": "https://example.com/story?utm_source=x"}])
    text = "<b>📡 Completely rewritten headline</b>\n"
    allowed, reason = publication_guard.check_before_publish(text, "https://example.com/story?utm_medium=y")
    assert not allowed
    assert reason == "canonical_url_already_published"


def test_same_event_rewrite_is_blocked_by_final_semantic_guard(tmp_path):
    _write_ledger(tmp_path, [{
        "title": "OpenAI launches GPT-6 Astra for work",
        "summary": "OpenAI launches GPT-6 Astra, a new model for workplace tasks.",
        "link": "https://example.com/old-openai",
    }])
    text = (
        "<b>📡 OpenAI رونمایی از GPT-6 Astra برای کار را اعلام کرد</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nOpenAI مدل GPT-6 Astra را برای کار معرفی کرده است.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(text, "https://another.example/openai")
    assert not allowed
    assert reason.startswith("semantic_story_already_published")


def test_distinct_story_about_same_entity_remains_publishable(tmp_path):
    _write_ledger(tmp_path, [{
        "title": "OpenAI launches GPT-6 Astra for work",
        "summary": "OpenAI launches GPT-6 Astra, a new model for workplace tasks.",
        "link": "https://example.com/old-openai",
    }])
    text = (
        "<b>📡 OpenAI announces a new research partnership in robotics</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nThe partnership focuses on robotics research and deployment.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(text, "https://example.com/robotics")
    assert allowed
    assert reason == "no_publication_conflict"


def test_leader_name_alone_does_not_block_a_different_event(tmp_path):
    _write_ledger(tmp_path, [{
        "title": "Sam Altman attends an AI policy summit in Washington",
        "summary": "Sam Altman discussed policy and governance at a Washington event.",
        "leader": "Sam Altman",
        "link": "https://example.com/washington",
    }])
    text = (
        "<b>📡 Sam Altman says OpenAI going public in 2026 would be ill-advised</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nSam Altman said an IPO in 2026 would be ill-advised for OpenAI.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(text, "https://example.com/ipo")
    assert allowed
    assert reason == "no_publication_conflict"
