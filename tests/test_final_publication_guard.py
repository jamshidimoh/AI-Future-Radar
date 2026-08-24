import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import publication_guard


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


def test_rewritten_story_is_blocked_by_final_semantic_guard(tmp_path):
    _write_ledger(tmp_path, [{
        "title": "Andrew Ng launches a new AI agents course",
        "summary": "A new course teaches developers how to build AI agents.",
        "leader": "Andrew Ng",
        "link": "https://example.com/old-course",
    }])
    text = (
        "<b>📡 New developer program teaches practical AI agent building</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nAndrew Ng's course focuses on building AI agents for developers.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(text, "https://another.example/course")
    assert not allowed
    assert reason.startswith("semantic_story_already_published")


def test_distinct_story_remains_publishable(tmp_path):
    _write_ledger(tmp_path, [{
        "title": "Andrew Ng launches a new AI agents course",
        "summary": "A new course teaches developers how to build AI agents.",
        "leader": "Andrew Ng",
        "link": "https://example.com/old-course",
    }])
    text = (
        "<b>📡 Andrew Ng announces a healthcare AI research initiative</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nThe initiative explores AI applications in healthcare research.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(text, "https://example.com/healthcare")
    assert allowed
    assert reason == "no_publication_conflict"
