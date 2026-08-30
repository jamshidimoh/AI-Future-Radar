"""Runtime acceptance guard for the production publication contract.

The bot may complete without an exception when selected candidates are rejected
by a downstream editorial/delivery gate. A production run is acceptable when
that rejection is explicitly evidenced and therefore results in fail-closed
zero publication. Unexpected zero publication after a candidate survives
editorial gates remains a production failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


CANDIDATE_PATTERNS = (
    re.compile(r"\[Production Selection\].*?total=(\d+)"),
    re.compile(r"\[Selection Timing\].*?candidates=(\d+)"),
)
CONTRACT_PATTERN = re.compile(
    r"\[Production Contract\].*?normal_news=(\d+).*?tier0_news=(\d+).*?education=(\w+)"
)
POSTS_SENT_PATTERN = re.compile(r"Posts sent:\s*(\d+)\s*/\s*(\d+)")
EDITORIAL_SKIP_PATTERN = re.compile(r"\[Editorial Gate\]\s+skipped candidate:")


def _last_match(lines, patterns):
    value = None
    for line in lines:
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                value = match
    return value


def validate(log_text: str) -> tuple[bool, str]:
    lines = log_text.splitlines()
    candidate_match = _last_match(lines, CANDIDATE_PATTERNS)
    contract_match = _last_match(lines, (CONTRACT_PATTERN,))
    posts_match = _last_match(lines, (POSTS_SENT_PATTERN,))

    if candidate_match is None:
        return False, "missing production candidate-count evidence"
    if contract_match is None:
        return False, "missing production contract summary"

    selected = int(candidate_match.group(1))
    normal_news = int(contract_match.group(1))
    tier0_news = int(contract_match.group(2))
    education = contract_match.group(3)
    published_news = normal_news + tier0_news
    editorial_rejections = sum(
        1 for line in lines if EDITORIAL_SKIP_PATTERN.search(line)
    )

    # Zero publication is valid when every selected candidate is explicitly
    # rejected by the downstream editorial gate: this is the required
    # fail-closed behavior. Do not treat a generic zero-publication run as OK.
    if selected > 0 and published_news == 0 and education != "confirmed":
        if editorial_rejections >= selected and (
            posts_match is None or int(posts_match.group(1)) == 0
        ):
            return True, (
                "production acceptance PASS: fail-closed editorial rejection; "
                f"selected={selected}, editorial_rejections={editorial_rejections}, "
                f"published_news={published_news}, education={education}"
            )
        return False, (
            "production contract violation: selected candidates existed but "
            "zero news items were confirmed and the run did not provide evidence "
            "that all selected candidates were explicitly rejected downstream "
            f"(selected={selected}, editorial_rejections={editorial_rejections}, "
            f"normal_news={normal_news}, tier0_news={tier0_news}, education={education})"
        )

    return True, (
        "production acceptance PASS: "
        f"selected={selected}, published_news={published_news}, education={education}"
    )


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("run.log")
    if not path.exists():
        print(f"[Production Acceptance] FAIL: missing log {path}")
        return 1
    ok, message = validate(path.read_text(encoding="utf-8", errors="replace"))
    prefix = "PASS" if ok else "FAIL"
    print(f"[Production Acceptance] {prefix}: {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
