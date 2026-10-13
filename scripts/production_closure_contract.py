"""Pure acceptance helpers for consecutive production-closure evidence."""
from __future__ import annotations

import re
from typing import Any

_SELECTED_PATTERNS = (
    re.compile(r"\[Publication Summary Budget\].*?output=(\d+)", re.I),
    re.compile(r"\[Unified Portfolio Selection\].*?candidates=(\d+)", re.I),
    re.compile(r"\[Selection Timing\].*?candidates=(\d+)", re.I),
    re.compile(r"\[Production Selection\].*?total=(\d+)", re.I),
)
_POSTS_SENT = re.compile(r"Posts sent:\s*(\d+)\s*/\s*(\d+)", re.I)


def selected_candidate_count(log_text: str) -> int | None:
    """Return the last effective selection count; prefer the post-budget count."""
    lines = str(log_text or "").splitlines()
    # The publication budget is the effective post-selection set. If present,
    # it takes precedence over earlier discovery/selection counters.
    for pattern in _SELECTED_PATTERNS:
        matches = [pattern.search(line) for line in lines]
        matches = [match for match in matches if match]
        if matches:
            return int(matches[-1].group(1))
    return None


def posts_sent_counts(log_text: str) -> tuple[int, int] | None:
    matches = [_POSTS_SENT.search(line) for line in str(log_text or "").splitlines()]
    matches = [match for match in matches if match]
    if not matches:
        return None
    match = matches[-1]
    return int(match.group(1)), int(match.group(2))


def publish_evidence(log_text: str) -> bool:
    """Require confirmed delivery, or a genuinely empty, accepted production run."""
    text = str(log_text or "")
    counts = posts_sent_counts(text)
    selected = selected_candidate_count(text)
    accepted = re.search(r"\[Production Acceptance\]\s+PASS:", text, re.I) is not None
    if counts is None or selected is None or not accepted:
        return False
    sent, total = counts
    confirmed_publication = (
        sent > 0
        and re.search(r"\[Telegram Published\]", text, re.I) is not None
    )
    if confirmed_publication:
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


def is_persisted_state_skip(run: dict[str, Any], bot_job: dict[str, Any] | None) -> bool:
    """Ignore only the workflow job intentionally skipped for state-only commits."""
    if not isinstance(bot_job, dict) or str(bot_job.get("conclusion") or "").lower() != "skipped":
        return False
    if str(run.get("event") or "").lower() != "push":
        return False
    head_commit = run.get("head_commit") or {}
    message = str(head_commit.get("message") or "")
    return message.startswith("chore: persist production state [skip ci]")
