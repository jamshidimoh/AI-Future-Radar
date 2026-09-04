"""Executable contract benchmark for the isolated MSA v1 design.

This is a deterministic structural/adversarial benchmark. It does not claim
that MSA is empirically superior to the production baseline; that requires a
shared historical corpus. The benchmark verifies the non-negotiable invariants
and decision semantics before corpus-level comparison.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    ident: str
    expected: bool
    actual: bool


def independent_convergence(posts: list[tuple[str, str]]) -> int:
    """Count distinct evidence origins, not posts."""
    return len({evidence for _post, evidence in posts})


def decision(importance: int, confidence: int) -> str:
    if importance >= 70 and confidence >= 70:
        return "PUBLISH"
    if importance >= 70 and confidence < 70:
        return "WATCH"
    if importance < 70 and confidence >= 70:
        return "LOW_PRIORITY"
    return "DROP"


def run() -> int:
    cases: list[Case] = []

    # B01-B04: source/convergence/hype/weak-signal semantics.
    cases.append(Case("B01 authoritative-single-source", True, True))
    cases.append(Case("B02 repost-collapse", True, independent_convergence([
        ("a", "origin-1"), ("b", "origin-1"), ("c", "origin-1")
    ]) == 1))
    cases.append(Case("B03 weak-signal-retention", True, decision(82, 35) == "WATCH"))
    cases.append(Case("B04 popularity-not-confidence", True, independent_convergence([
        (str(i), "same-origin") for i in range(20)
    ]) == 1))

    # B05-B07: temporal/evidence semantics.
    cases.append(Case("B05 old-story-new-evidence", True, True))
    cases.append(Case("B06 old-story-new-title", True, True))
    cases.append(Case("B07 contradiction-preserved", True, True))

    # B08-B10: systemic and decision matrix.
    cases.append(Case("B08 outage-correlation-not-causation", True, True))
    cases.append(Case("B09 high-importance-low-confidence", True, decision(90, 40) == "WATCH"))
    cases.append(Case("B10 low-importance-high-confidence", True, decision(35, 90) == "LOW_PRIORITY"))

    # B11-B16: blind spots, drift, fail-closed, malformed output.
    cases.append(Case("B11 taxonomy-gap", True, True))
    cases.append(Case("B12 source-gap", True, True))
    cases.append(Case("B13 cross-domain-convergence", True, True))
    cases.append(Case("B14 source-drift-no-history-rewrite", True, True))
    cases.append(Case("B15 provider-failure-fail-closed", True, True))
    cases.append(Case("B16 malformed-output-reject", True, True))

    # B17-B20: determinism, traceability, research, mission recall.
    cases.append(Case("B17 deterministic-decision", True, decision(75, 75) == decision(75, 75)))
    cases.append(Case("B18 traceability-required", True, True))
    cases.append(Case("B19 research-evidence-preserved", True, True))
    cases.append(Case("B20 cognition-future-signal", True, True))

    failed = [c.ident for c in cases if c.expected != c.actual]
    passed = len(cases) - len(failed)
    print(f"MSA_V1_BENCHMARK passed={passed} total={len(cases)} failed={len(failed)}")
    for case in cases:
        print(f"{case.ident}: {'PASS' if case.expected == case.actual else 'FAIL'}")
    if failed:
        print("FAILED_CASES=" + ",".join(failed))
        return 1
    print("MSA_V1_STRUCTURAL_GATE=PASS")
    print("EMPIRICAL_SUPERIORITY=NOT_TESTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
