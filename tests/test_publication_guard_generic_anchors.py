import json
from pathlib import Path

import src.publication_guard as publication_guard


def _write_ledger(tmp_path, records):
    path = tmp_path / "telegram_feedback.json"
    path.write_text(
        json.dumps({"version": 2, "messages": {str(i): record for i, record in enumerate(records)}}, ensure_ascii=False),
        encoding="utf-8",
    )
    publication_guard.LEDGER_PATH = path


def test_three_shared_anchors_without_semantic_match_are_not_enough(tmp_path):
    _write_ledger(tmp_path, [{
        "title": "OpenAI launches GPT-6 for workplace tasks",
        "summary": "OpenAI launches GPT-6 for workplace tasks and enterprise deployment.",
        "link": "https://example.com/old",
    }])
    text = (
        "<b>📡 OpenAI partners with NVIDIA on a new robotics infrastructure program</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nOpenAI and NVIDIA will build a robotics infrastructure program for autonomous systems.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(text, "https://example.com/new")
    assert allowed
    assert reason == "no_publication_conflict"
