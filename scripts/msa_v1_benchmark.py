"""Deterministic corpus-level benchmark for MSA v1.

The corpus is a controlled benchmark fixture, not a historical production
corpus. It compares a conventional popularity/recency baseline with MSA's
separate importance/confidence, evidence, convergence and fail-closed rules.
It must not be interpreted as proof of real-world superiority until evaluated
on an independently curated historical corpus.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class Row:
    ident: str
    importance: int
    confidence: int
    recency: int
    popularity: int
    independent_evidence: int
    evidence_quality: int
    contradiction: bool
    taxonomy_hit: bool
    source_reliable: bool
    malformed: bool
    gold: str


def independent_convergence(posts: list[tuple[str, str]]) -> int:
    return len({evidence for _post, evidence in posts})


def decision(importance: int, confidence: int) -> str:
    if importance >= 70 and confidence >= 70:
        return "PUBLISH"
    if importance >= 70 and confidence < 70:
        return "WATCH"
    if importance < 70 and confidence >= 70:
        return "LOW_PRIORITY"
    return "DROP"


def msa_decision(row: Row) -> str:
    # Fail closed before ranking.
    if row.malformed or not row.taxonomy_hit or not row.source_reliable:
        return "DROP"
    # Contradictory evidence reduces confidence but does not erase the story.
    confidence = row.confidence
    if row.contradiction:
        confidence = min(confidence, 55)
    # Independent evidence is required for high-confidence convergence.
    if row.independent_evidence >= 2 and row.evidence_quality >= 70:
        confidence = max(confidence, 75)
    return decision(row.importance, confidence)


def baseline_decision(row: Row) -> str:
    # Conventional ranker: importance is blended with popularity/recency.
    # It does not explicitly separate evidence, convergence or provider safety.
    score = round(0.55 * row.importance + 0.25 * row.popularity + 0.20 * row.recency)
    if score >= 70:
        return "PUBLISH"
    if score >= 55:
        return "WATCH"
    if score >= 40:
        return "LOW_PRIORITY"
    return "DROP"


def macro_f1(rows: list[Row], predictions: list[str]) -> float:
    labels = ["PUBLISH", "WATCH", "LOW_PRIORITY", "DROP"]
    values: list[float] = []
    for label in labels:
        tp = sum(r.gold == label and p == label for r, p in zip(rows, predictions))
        fp = sum(r.gold != label and p == label for r, p in zip(rows, predictions))
        fn = sum(r.gold == label and p != label for r, p in zip(rows, predictions))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return mean(values)


CORPUS = [
    Row("B01", 88, 92, 80, 35, 1, 90, False, True, True, False, "PUBLISH"),
    Row("B02", 84, 82, 90, 98, 1, 72, False, True, True, False, "PUBLISH"),
    Row("B03", 82, 35, 70, 15, 1, 45, False, True, True, False, "WATCH"),
    Row("B04", 78, 40, 95, 99, 1, 40, False, True, True, False, "WATCH"),
    Row("B05", 86, 88, 20, 45, 2, 85, False, True, True, False, "PUBLISH"),
    Row("B06", 86, 88, 85, 60, 1, 85, False, True, True, False, "PUBLISH"),
    Row("B07", 90, 80, 75, 75, 2, 60, True, True, True, False, "WATCH"),
    Row("B08", 92, 78, 80, 92, 3, 78, False, True, True, False, "PUBLISH"),
    Row("B09", 90, 40, 80, 88, 1, 45, False, True, True, False, "WATCH"),
    Row("B10", 35, 90, 85, 70, 1, 90, False, True, True, False, "LOW_PRIORITY"),
    Row("B11", 80, 82, 70, 30, 1, 78, False, False, True, False, "DROP"),
    Row("B12", 82, 75, 70, 35, 1, 75, False, True, False, False, "DROP"),
    Row("B13", 88, 78, 70, 45, 3, 82, False, True, True, False, "PUBLISH"),
    Row("B14", 75, 76, 60, 40, 2, 74, False, True, True, False, "PUBLISH"),
    Row("B15", 86, 90, 70, 80, 2, 88, False, True, True, True, "DROP"),
    Row("B16", 85, 85, 80, 90, 1, 80, False, True, True, True, "DROP"),
    Row("B17", 75, 75, 65, 50, 2, 75, False, True, True, False, "PUBLISH"),
    Row("B18", 78, 80, 65, 45, 2, 80, False, True, True, False, "PUBLISH"),
    Row("B19", 95, 94, 55, 25, 2, 96, False, True, True, False, "PUBLISH"),
    Row("B20", 84, 72, 60, 35, 2, 78, False, True, True, False, "PUBLISH"),
]


def structural_gate() -> bool:
    cases = [
        decision(82, 35) == "WATCH",
        decision(90, 40) == "WATCH",
        decision(35, 90) == "LOW_PRIORITY",
        independent_convergence([(str(i), "same-origin") for i in range(20)]) == 1,
        independent_convergence([("a", "o1"), ("b", "o1"), ("c", "o2")]) == 2,
    ]
    return all(cases)


def run() -> int:
    msa = [msa_decision(r) for r in CORPUS]
    baseline = [baseline_decision(r) for r in CORPUS]
    msa_correct = sum(p == r.gold for r, p in zip(CORPUS, msa))
    baseline_correct = sum(p == r.gold for r, p in zip(CORPUS, baseline))
    msa_f1 = macro_f1(CORPUS, msa)
    baseline_f1 = macro_f1(CORPUS, baseline)

    print(f"MSA_V1_CORPUS rows={len(CORPUS)}")
    print(f"BASELINE accuracy={baseline_correct/len(CORPUS):.3f} macro_f1={baseline_f1:.3f}")
    print(f"MSA_V1 accuracy={msa_correct/len(CORPUS):.3f} macro_f1={msa_f1:.3f}")
    print(f"MSA_V1_DELTA accuracy={(msa_correct-baseline_correct)/len(CORPUS):+.3f} macro_f1={msa_f1-baseline_f1:+.3f}")

    failed = [r.ident for r, p in zip(CORPUS, msa) if p != r.gold]
    print(f"MSA_V1_CORPUS_GATE={'PASS' if not failed else 'FAIL'}")
    if failed:
        print("CORPUS_FAILED=" + ",".join(failed))
        return 1
    if not structural_gate():
        print("MSA_V1_STRUCTURAL_GATE=FAIL")
        return 1
    print("MSA_V1_STRUCTURAL_GATE=PASS")
    print("EMPIRICAL_SUPERIORITY=CONTROLLED_FIXTURE_ONLY")
    print("HISTORICAL_CORPUS_VALIDATION=NOT_TESTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
