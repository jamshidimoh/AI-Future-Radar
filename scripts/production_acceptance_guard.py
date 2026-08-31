"""Runtime acceptance guard for the production publication contract.

A selected candidate must end in an auditable terminal state: publication,
explicit editorial rejection, or an upstream structural rejection such as
canonical-story deduplication. Protected Tier-0 publication is a valid
failover path only when every non-published selected candidate is fully
accounted for as rejected upstream/editorially.
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
    r"\[Production Contract\].*?normal_news=(\d+).*?normal_max=(\d+).*?tier0_news=(\d+).*?tier0_quota_exempt=(\w+).*?education=(\w+)"
)
POSTS_SENT_PATTERN = re.compile(r"Posts sent:\s*(\d+)\s*/\s*(\d+)")
EDITORIAL_SKIP_PATTERN = re.compile(r"\[Editorial Gate\]\s+skipped candidate:")
TIER0_PRIORITY_PATTERN = re.compile(r"\[Tier0 Interview Priority\]\s+retained=(\d+).*?quota_exempt=true")
TIER0_PUBLICATION_PATTERN = re.compile(r"\[Publication Policy\]\s+PUBLISH TIER0\b")


def _last_match(lines, patterns):
    value = None
    for line in lines:
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                value = match
    return value


def _last_group_int(lines, pattern):
    value = 0
    found = False
    for line in lines:
        match = pattern.search(line)
        if match:
            value = int(match.group(1))
            found = True
    return value if found else None


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
    normal_max = int(contract_match.group(2))
    tier0_news = int(contract_match.group(3))
    tier0_quota_exempt = contract_match.group(4).lower() == "true"
    education = contract_match.group(5)
    published_news = normal_news + tier0_news
    editorial_rejections = sum(1 for line in lines if EDITORIAL_SKIP_PATTERN.search(line))

    protected_blocked = _last_group_int(lines, re.compile(r"protected_same_story_blocked=(\d+)")) or 0
    canonical_story_rejected = _last_group_int(lines, re.compile(r"\[Canonical Story Gate\].*?story_rejected=(\d+)")) or 0
    canonical_semantic_rejected = _last_group_int(lines, re.compile(r"\[Canonical Story Gate\].*?semantic_rejected=(\d+)")) or 0
    canonical_url_rejected = _last_group_int(lines, re.compile(r"\[Canonical Story Gate\].*?url_rejected=(\d+)")) or 0
    upstream_rejections = max(
        protected_blocked,
        canonical_story_rejected + canonical_semantic_rejected + canonical_url_rejected,
    )
    accounted = published_news + editorial_rejections + upstream_rejections
    posts_sent = int(posts_match.group(1)) if posts_match else None
    tier0_retained = _last_group_int(lines, TIER0_PRIORITY_PATTERN) or 0
    tier0_publish_policy = bool(_last_match(lines, (TIER0_PUBLICATION_PATTERN,)))

    if selected > 0 and published_news == 0 and education != "confirmed":
        if accounted >= selected and (posts_sent is None or posts_sent == 0):
            return True, (
                "production acceptance PASS: fail-closed editorial rejection/accounting verified; "
                f"selected={selected}, published={published_news}, editorial_rejections={editorial_rejections}, "
                f"upstream_rejections={upstream_rejections}, education={education}"
            )
        return False, (
            "production contract violation: zero news items were published and the selected set "
            "did not provide evidence of publication or explicit rejection; "
            f"selected={selected}, published={published_news}, editorial_rejections={editorial_rejections}, "
            f"upstream_rejections={upstream_rejections}, accounted={accounted}, education={education}"
        )

    if published_news > 0 and normal_news == 0 and tier0_news > 0:
        unaccounted_selected = max(0, selected - published_news)
        rejection_accounting = editorial_rejections + upstream_rejections
        if (
            not tier0_quota_exempt
            or tier0_retained <= 0
            or not tier0_publish_policy
            or rejection_accounting < unaccounted_selected
        ):
            return False, (
                "production contract violation: Tier-0-only publication lacked complete fallback accounting; "
                f"selected={selected}, unaccounted_selected={unaccounted_selected}, "
                f"rejection_accounting={rejection_accounting}, tier0_news={tier0_news}, tier0_retained={tier0_retained}, "
                f"tier0_quota_exempt={tier0_quota_exempt}, tier0_publish_policy={tier0_publish_policy}"
            )
        return True, (
            "production acceptance PASS: protected Tier-0 fallback with complete selected-set accounting; "
            f"selected={selected}, normal_news={normal_news}, tier0_news={tier0_news}, "
            f"normal_max={normal_max}, rejection_accounting={rejection_accounting}, education={education}"
        )

    return True, f"production acceptance PASS: selected={selected}, published_news={published_news}, education={education}"


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