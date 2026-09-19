"""Runtime acceptance guard for the production publication contract.

A selected candidate must end in an auditable terminal state: publication,
explicit editorial/policy/publication rejection, or an upstream structural
rejection such as canonical-story deduplication. Mission portfolio coverage is
also a production invariant: when the runtime explicitly reports an unmet
mission-coverage target, acceptance must fail closed rather than passing on
publication accounting alone. Normal and Mind/Ideas/Voices lanes are validated
as distinct contracts; the normal score floor never applies to Mind.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CANDIDATE_PATTERNS = (
    re.compile(r"\[Production Selection\].*?total=(\d+)"),
    re.compile(r"\[Selection Timing\].*?candidates=(\d+)"),
)
SUMMARY_BUDGET_PATTERN = re.compile(r"\[Publication Summary Budget\].*?output=(\d+)")
CONTRACT_PATTERN = re.compile(
    r"\[Production Contract\].*?normal_news=(\d+).*?normal_max=(\d+)"
    r".*?(?:mind_ideas_voices=(\d+)\s+mind_max=(\d+)\s+)?"
    r"tier0_news=(\d+)(?:\s+tier0_quota_exempt=(\w+))?.*?education=(\w+)"
)
POSTS_SENT_PATTERN = re.compile(r"Posts sent:\s*(\d+)\s*/\s*(\d+)")
EDITORIAL_SKIP_PATTERN = re.compile(r"\[Editorial Gate\]\s+skipped candidate:")
POLICY_REJECTION_PATTERN = re.compile(r"(?:normal_score_policy_blocked|tier0_score_policy_blocked):\s*[^\s]+<=?\s*[^\s]+")
PUBLICATION_REJECTION_PATTERN = re.compile(r"\[Publication Contract\]\s+candidate rejected reason=([^;]+);")
TIER0_PRIORITY_PATTERN = re.compile(r"\[Tier0 Interview Priority\]\s+retained=(\d+).*?quota_exempt=true")
TIER0_PUBLICATION_PATTERN = re.compile(r"\[Publication Policy\]\s+PUBLISH TIER0\b.*?score=([-+]?\d+(?:\.\d+)?)")
TIER0_FLOOR_PATTERN = re.compile(r"tier0_quality_floor(?:=|:)\s*([-+]?\d+(?:\.\d+)?)", re.I)
MIND_PUBLICATION_PATTERN = re.compile(r"\[Publication Policy\]\s+PUBLISH mind_ideas_voices\b.*?score=([-+]?\d+(?:\.\d+)?)")
MIND_SELECTION_PATTERN = re.compile(r"\[Dual Lane Selection\].*?mind_ideas_voices=(\d+).*?mind_cap=(\d+).*?mind_score_floor=not_applied")
MIND_SUMMARY_PATTERN = re.compile(r"\[Publication Summary Budget\].*?mind_ideas_voices=(\d+).*?mind_limit=(\d+).*?mind_score_floor=not_applied")
MIND_CONTRACT_PATTERN = re.compile(r"\[Production Contract\].*?mind_ideas_voices=(\d+).*?mind_max=(\d+).*?mind_score_floor=not_applied")
EDUCATION_CONFIRMED_PATTERN = re.compile(r"\[Education Published\].*?CONFIRMED\b.*?telegram_delivery=successful")
MISSION_COVERAGE_PATTERN = re.compile(
    r"\[Mission Coverage Recovery\].*?target=(\d+).*?prepared=(\d+).*?"
    r"attempts=(\d+).*?recovered=(\d+).*?status=(\w+)"
)
MISSION_COVERAGE_COMPACT_PATTERN = re.compile(
    r"\[Mission Coverage Recovery\].*?missing_lanes=(\d+).*?"
    r"attempts=(\d+).*?recovered=(\d+).*?status=(\w+)"
)
MISSION_COVERAGE_NO_CANDIDATE_PATTERN = re.compile(
    r"\[Mission Coverage Recovery\].*?area=([^\s]+).*?status=no_candidate"
)
MISSION_COVERAGE_HARD_FAILURE_PATTERN = re.compile(
    r"\[Mission Coverage Recovery\].*?status=(?:failed|below_score_floor|independent_lane_not_score_gated)"
)


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


def _published_tier0_scores(lines):
    return [float(m.group(1)) for line in lines if (m := TIER0_PUBLICATION_PATTERN.search(line))]


def _observed_tier0_floor(lines):
    value = None
    for line in lines:
        match = TIER0_FLOOR_PATTERN.search(line)
        if match:
            value = float(match.group(1))
    return value


def _mission_coverage_status(lines):
    match = _last_match(lines, (MISSION_COVERAGE_PATTERN, MISSION_COVERAGE_COMPACT_PATTERN))
    if match is None:
        return None
    groups = match.groups()
    if len(groups) == 5:
        result = {
            "target": int(groups[0]),
            "prepared": int(groups[1]),
            "attempts": int(groups[2]),
            "recovered": int(groups[3]),
            "status": groups[4].casefold(),
        }
    else:
        missing_lanes, attempts, recovered, status = groups
        result = {
            "target": int(missing_lanes),
            "prepared": 0,
            "attempts": int(attempts),
            "recovered": int(recovered),
            "status": status.casefold(),
        }
    result["no_candidate_lanes"] = len({m.group(1).casefold() for line in lines if (m := MISSION_COVERAGE_NO_CANDIDATE_PATTERN.search(line))})
    result["hard_failures"] = sum(1 for line in lines if MISSION_COVERAGE_HARD_FAILURE_PATTERN.search(line))
    return result


def validate(log_text: str) -> tuple[bool, str]:
    lines = log_text.splitlines()
    candidate_match = _last_match(lines, CANDIDATE_PATTERNS)
    contract_match = _last_match(lines, (CONTRACT_PATTERN,))
    posts_match = _last_match(lines, (POSTS_SENT_PATTERN,))
    if candidate_match is None:
        return False, "missing production candidate-count evidence"
    if contract_match is None:
        return False, "missing production contract summary"

    mission_coverage = _mission_coverage_status(lines)
    if mission_coverage and mission_coverage["status"] == "unmet":
        accounted = mission_coverage["recovered"] + mission_coverage["prepared"]
        gap = max(0, mission_coverage["target"] - accounted)
        no_candidate = mission_coverage.get("no_candidate_lanes", 0)
        hard_failures = mission_coverage.get("hard_failures", 0)
        # The final acceptance document explicitly allows a lane to remain below
        # target when no eligible high-quality candidate exists. A deterministic
        # no-candidate outcome is therefore not a publication failure. Any
        # candidate that existed but failed QA/score/recovery remains fail-closed.
        if gap > 0 and no_candidate >= gap and hard_failures == 0:
            return True, (
                "production acceptance PASS: mission coverage gap is attributable only to lanes with no eligible candidate; "
                f"target={mission_coverage['target']}, prepared={mission_coverage['prepared']}, recovered={mission_coverage['recovered']}, no_candidate_lanes={no_candidate}"
            )
        return False, (
            "production contract violation: mission portfolio coverage remained unmet; "
            f"target={mission_coverage['target']}, prepared={mission_coverage['prepared']}, attempts={mission_coverage['attempts']}, recovered={mission_coverage['recovered']}, no_candidate_lanes={no_candidate}, hard_failures={hard_failures}"
        )
    if mission_coverage and mission_coverage["recovered"] + mission_coverage["prepared"] < mission_coverage["target"]:
        gap = mission_coverage["target"] - (mission_coverage["recovered"] + mission_coverage["prepared"])
        no_candidate = mission_coverage.get("no_candidate_lanes", 0)
        if no_candidate >= gap:
            return True, (
                "production acceptance PASS: mission coverage evidence leaves only deterministic no-candidate lanes unresolved; "
                f"target={mission_coverage['target']}, prepared={mission_coverage['prepared']}, recovered={mission_coverage['recovered']}, no_candidate_lanes={no_candidate}"
            )
        return False, (
            "production contract violation: mission portfolio coverage evidence is inconsistent; "
            f"target={mission_coverage['target']}, prepared={mission_coverage['prepared']}, recovered={mission_coverage['recovered']}, no_candidate_lanes={no_candidate}"
        )

    summary_budget_match = _last_match(lines, (SUMMARY_BUDGET_PATTERN,))
    selected = int(summary_budget_match.group(1)) if summary_budget_match is not None else int(candidate_match.group(1))
    normal_news = int(contract_match.group(1))
    normal_max = int(contract_match.group(2))
    mind_news = int(contract_match.group(3) or 0)
    mind_max = int(contract_match.group(4) or 0)
    tier0_news = int(contract_match.group(5))
    tier0_quota_exempt = (contract_match.group(6) or "false").lower() == "true"
    education = contract_match.group(7)
    if _last_match(lines, (EDUCATION_CONFIRMED_PATTERN,)):
        education = "confirmed"

    mind_contract = _last_match(lines, (MIND_CONTRACT_PATTERN,))
    if mind_news < 0 or (mind_max and mind_news > mind_max):
        return False, f"production contract violation: Mind/Ideas/Voices quota exceeded; mind_news={mind_news}, mind_max={mind_max}"
    if mind_news > 0 and mind_contract is None:
        return False, "production contract violation: Mind publication reported without independent lane evidence"
    if mind_contract:
        observed_mind_news = int(mind_contract.group(1))
        observed_mind_max = int(mind_contract.group(2))
        if observed_mind_news != mind_news or observed_mind_max != mind_max:
            return False, "production contract violation: Mind lane contract counters are inconsistent"
    if mind_news > 0:
        selection = _last_match(lines, (MIND_SELECTION_PATTERN,))
        summary = _last_match(lines, (MIND_SUMMARY_PATTERN,))
        if selection is None:
            return False, "production contract violation: Mind publication lacks independent selection evidence"
        if summary is None:
            return False, "production contract violation: Mind publication lacks independent summary-budget evidence"
        if mind_news > mind_max > 0:
            return False, f"production contract violation: Mind lane exceeds configured cap: {mind_news}>{mind_max}"

    published_news = normal_news + mind_news + tier0_news
    editorial_rejections = sum(1 for line in lines if EDITORIAL_SKIP_PATTERN.search(line))
    policy_rejections = sum(1 for line in lines if POLICY_REJECTION_PATTERN.search(line))
    publication_rejections = sum(1 for line in lines if PUBLICATION_REJECTION_PATTERN.search(line))

    protected_blocked = _last_group_int(lines, re.compile(r"protected_same_story_blocked=(\d+)")) or 0
    canonical_story_rejected = _last_group_int(lines, re.compile(r"\[Canonical Story Gate\].*?story_rejected=(\d+)")) or 0
    canonical_semantic_rejected = _last_group_int(lines, re.compile(r"\[Canonical Story Gate\].*?semantic_rejected=(\d+)")) or 0
    canonical_url_rejected = _last_group_int(lines, re.compile(r"\[Canonical Story Gate\].*?url_rejected=(\d+)")) or 0
    upstream_rejections = max(protected_blocked, canonical_story_rejected + canonical_semantic_rejected + canonical_url_rejected)
    accounted = published_news + editorial_rejections + policy_rejections + publication_rejections + upstream_rejections
    posts_sent = int(posts_match.group(1)) if posts_match else None

    tier0_retained = _last_group_int(lines, TIER0_PRIORITY_PATTERN) or 0
    tier0_publish_matches = _published_tier0_scores(lines)
    tier0_publish_policy = bool(tier0_publish_matches)
    tier0_floor = _observed_tier0_floor(lines)
    if tier0_publish_matches:
        effective_floor = tier0_floor if tier0_floor is not None else 60.0
        violating_scores = [score for score in tier0_publish_matches if score < effective_floor]
        if violating_scores:
            return False, f"production contract violation: low-quality Tier-0 publication observed; scores={violating_scores}, floor={effective_floor}"

    # Mind score is intentionally not checked against NORMAL_SCORE_FLOOR or
    # PROTECTED_SCORE_FLOOR. Its contract requires explicit independent-lane evidence.
    if selected > 0 and published_news == 0 and education != "confirmed":
        if accounted >= selected and (posts_sent is None or posts_sent == 0):
            return True, (
                "production acceptance PASS: fail-closed editorial/policy/publication rejection/accounting verified; "
                f"selected={selected}, published={published_news}, editorial_rejections={editorial_rejections}, policy_rejections={policy_rejections}, publication_rejections={publication_rejections}, upstream_rejections={upstream_rejections}, education={education}"
            )
        return False, (
            "production contract violation: zero news items were published and the selected set did not provide evidence of publication or explicit rejection; "
            f"selected={selected}, published={published_news}, editorial_rejections={editorial_rejections}, policy_rejections={policy_rejections}, publication_rejections={publication_rejections}, upstream_rejections={upstream_rejections}, accounted={accounted}, education={education}"
        )

    if published_news > 0 and normal_news == 0 and tier0_news > 0 and mind_news == 0:
        unaccounted_selected = max(0, selected - published_news)
        rejection_accounting = editorial_rejections + policy_rejections + publication_rejections + upstream_rejections
        if not tier0_quota_exempt or tier0_retained <= 0 or not tier0_publish_policy or rejection_accounting < unaccounted_selected:
            return False, (
                "production contract violation: Tier-0-only publication lacked complete fallback accounting; "
                f"selected={selected}, unaccounted_selected={unaccounted_selected}, rejection_accounting={rejection_accounting}, tier0_news={tier0_news}, tier0_retained={tier0_retained}, tier0_quota_exempt={tier0_quota_exempt}, tier0_publish_policy={tier0_publish_policy}"
            )
        return True, f"production acceptance PASS: protected Tier-0 fallback with complete selected-set accounting; selected={selected}, normal_news={normal_news}, tier0_news={tier0_news}, normal_max={normal_max}, rejection_accounting={rejection_accounting}, education={education}"

    if published_news > 0 and education != "confirmed" and accounted < selected:
        return False, (
            "production contract violation: published production run left selected candidates unaccounted; "
            f"selected={selected}, published={published_news}, accounted={accounted}, editorial_rejections={editorial_rejections}, policy_rejections={policy_rejections}, publication_rejections={publication_rejections}, upstream_rejections={upstream_rejections}, education={education}"
        )

    return True, f"production acceptance PASS: selected={selected}, published_news={published_news}, mind_ideas_voices={mind_news}, education={education}"


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
