import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import publication_guard


def test_cross_language_rewrite_is_blocked_before_delivery(tmp_path):
    path = tmp_path / "telegram_feedback.json"
    path.write_text(json.dumps({
        "version": 2,
        "messages": {"1": {
            "title": "Coursera backs co-founder Andrew Ng’s new AI education firm with $100 million investment",
            "summary": "Coursera is investing $100 million in Andrew Ng's new AI education firm.",
            "link": "https://example.com/coursera-andrew-ng",
        }}}, ensure_ascii=False), encoding="utf-8")
    publication_guard.LEDGER_PATH = path
    text = (
        "<b>📡 سرمایه‌گذاری ۱۰۰ میلیون دلاری Coursera در شرکت آموزشی جدید Andrew Ng</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nCoursera از شرکت آموزشی جدید Andrew Ng با سرمایه‌گذاری ۱۰۰ میلیون دلاری حمایت می‌کند.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(text, "https://example.com/new-rewrite")
    assert not allowed
    assert reason.startswith("semantic_story_already_published")


def test_distinct_story_about_same_person_is_not_blocked(tmp_path):
    path = tmp_path / "telegram_feedback.json"
    path.write_text(json.dumps({
        "version": 2,
        "messages": {"1": {
            "title": "Andrew Ng launches a new AI agents course",
            "summary": "A new course teaches developers how to build AI agents.",
            "link": "https://example.com/old-course",
        }}}, ensure_ascii=False), encoding="utf-8")
    publication_guard.LEDGER_PATH = path
    text = (
        "<b>📡 Andrew Ng announces a healthcare AI research initiative</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nThe initiative explores AI applications in healthcare research.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(text, "https://example.com/healthcare")
    assert allowed
    assert reason == "no_publication_conflict"
