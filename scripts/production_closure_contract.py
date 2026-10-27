"""Pure acceptance helpers for consecutive production-closure evidence."""
from __future__ import annotations

import re
from typing import Any

from src.people_bootstrap_contract import people_bootstrap_state_complete as _people_bootstrap_state_complete

_SELECTED_PATTERNS = (
    re.compile(r"\[Publication Summary Budget\].*?output(?:_news)?=(\d+)", re.I),
    re.compile(r"\[Unified Portfolio Selection\].*?candidates=(\d+)", re.I),
    re.compile(r"\[Selection Timing\].*?candidates=(\d+)", re.I),
    re.compile(r"\[Production Selection\].*?total=(\d+)", re.I),
)
_POSTS_SENT = re.compile(r"Posts sent:\s*(\d+)\s*/\s*(\d+)", re.I)


def selected_candidate_count(log_text: str) -> int | None:
    """Return post-budget output count, else the last runtime selection count."""
    lines = str(log_text or "").splitlines()
    budget_pattern = _SELECTED_PATTERNS[0]
    budget_matches = [
        (index, match)
        for index, line in enumerate(lines)
        if (match := budget_pattern.search(line))
    ]
    if budget_matches:
        return int(budget_matches[-1][1].group(1))
    fallback = []
    for index, line in enumerate(lines):
        for pattern in _SELECTED_PATTERNS[1:]:
            match = pattern.search(line)
            if match:
                fallback.append((index, match))
    if not fallback:
        return None
    return int(max(fallback, key=lambda item: item[0])[1].group(1))


def posts_sent_counts(log_text: str) -> tuple[int, int] | None:
    matches = [_POSTS_SENT.search(line) for line in str(log_text or "").splitlines()]
    matches = [match for match in matches if match]
    if not matches:
        return None
    match = matches[-1]
    return int(match.group(1)), int(match.group(2))


def publish_evidence(log_text: str) -> bool:
    """Require confirmed news/education delivery or a genuinely empty accepted run."""
    text = str(log_text or "")
    counts = posts_sent_counts(text)
    selected = selected_candidate_count(text)
    accepted = re.search(r"\[Production Acceptance\]\s+PASS:", text, re.I) is not None
    if counts is None or selected is None or not accepted:
        return False
    sent, total = counts
    confirmed_news_delivery = (
        sent > 0
        and re.search(r"\[Telegram Published\]", text, re.I) is not None
    )
    confirmed_education_delivery = (
        re.search(
            r"\[Education Published\]\s+CONFIRMED\b.*?telegram_delivery=successful",
            text,
            re.I,
        )
        is not None
    )
    if confirmed_news_delivery or confirmed_education_delivery:
        return True
    # Zero publication is valid only when no item was selected for publication;
    # explicit downstream rejections do not excuse losing the entire selected set.
    zero_candidate_run = (
        selected == 0
        and sent == 0
        and total == 0
        and re.search(r"\[Production Contract\].*?normal_news=0.*?tier0_news=0", text, re.I) is not None
    )
    return zero_candidate_run


_RUNTIME_SOURCE_REVISION = re.compile(
    r"\[Production Source Revision\]\s+event_sha=([0-9a-f]{40})\s+checkout_sha=([0-9a-f]{40})",
    re.I,
)


def source_revision_matches_event(log_text: str, expected_sha: Any) -> bool:
    """Require runtime logs to prove the checked-out source equals the event SHA."""
    matches = _RUNTIME_SOURCE_REVISION.findall(str(log_text or ""))
    if not matches:
        return False
    event_sha, checkout_sha = matches[-1]
    expected = str(expected_sha or "").strip().casefold()
    return bool(expected) and event_sha.casefold() == expected and checkout_sha.casefold() == expected


def people_bootstrap_state_complete(state: Any) -> bool:
    """Public closure-contract wrapper for the shared runtime state validator."""
    return _people_bootstrap_state_complete(state)


def is_completed_production_attempt(run: Any) -> bool:
    """Only completed workflow attempts belong in the closure evidence window.

    Queued and in-progress runs have no final conclusion or completed run-bot job.
    Counting them lets an unrelated newer queued run invalidate the completed run
    that triggered closure evaluation. Completed failures and cancellations remain
    evidence and must still block closure.
    """
    return isinstance(run, dict) and str(run.get("status") or "").casefold() == "completed"


def is_persisted_state_skip(run: dict[str, Any], bot_job: dict[str, Any] | None) -> bool:
    """Ignore only the workflow job intentionally skipped for state-only commits."""
    if not isinstance(bot_job, dict) or str(bot_job.get("conclusion") or "").lower() != "skipped":
        return False
    if str(run.get("event") or "").lower() != "push":
        return False
    head_commit = run.get("head_commit") or {}
    message = str(head_commit.get("message") or "")
    return message.startswith("chore: persist production state [skip ci]")



def health_snapshot_fresh(state: Any, run_started_at: Any) -> bool:
    """Require persisted health state to be updated no earlier than the latest run."""
    from datetime import datetime

    from scripts.llm_health_state_merge import snapshot_time

    if not isinstance(state, dict):
        return False
    started_text = str(run_started_at or "").strip()
    if not started_text:
        return False
    try:
        started = datetime.fromisoformat(started_text.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return False
    updated = snapshot_time(state)
    return updated > 0 and updated >= started
