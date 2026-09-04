"""Audit the real historical feedback corpus for MSA benchmark readiness.

This is intentionally a readiness gate, not a superiority benchmark. Historical
Telegram feedback contains real published metadata but no trustworthy gold labels
for rejection, importance, relevance, or expected decisions. The audit therefore
measures corpus availability/integrity and refuses to manufacture labels.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REQUIRED_METADATA = ("source", "title", "link", "content_type")


def main() -> int:
    path = Path("data/telegram_feedback.json")
    if not path.exists():
        print("HISTORICAL_CORPUS=ABSENT")
        print("HISTORICAL_CORPUS_VALIDATION=BLOCKED_NO_CORPUS")
        return 1

    payload = json.loads(path.read_text(encoding="utf-8"))
    messages = payload.get("messages", {})
    rows = [v for v in messages.values() if isinstance(v, dict)]
    valid = []
    invalid = 0
    links = set()
    for row in rows:
        missing = [k for k in REQUIRED_METADATA if not str(row.get(k) or "").strip()]
        link = str(row.get("link") or "").strip()
        if missing or not link:
            invalid += 1
            continue
        valid.append(row)
        links.add(link)

    content_types = Counter(str(r.get("content_type") or "news") for r in valid)
    sources = Counter(str(r.get("source") or "") for r in valid)
    duplicates = len(valid) - len(links)

    print(f"HISTORICAL_CORPUS records={len(rows)} valid_metadata={len(valid)} invalid={invalid}")
    print(f"HISTORICAL_CORPUS unique_links={len(links)} exact_link_duplicates={duplicates}")
    print("HISTORICAL_CONTENT_TYPES=" + ",".join(f"{k}:{v}" for k, v in sorted(content_types.items())))
    print(f"HISTORICAL_SOURCES={len(sources)}")

    # A real benchmark requires independent labels. Published status alone is not
    # a gold label, so fail closed rather than silently turning history into truth.
    labeled = Path("data/golden_dataset.jsonl")
    if not labeled.exists():
        print("GOLDEN_DATASET=ABSENT")
        print("HISTORICAL_CORPUS_VALIDATION=BLOCKED_NO_GOLD_LABELS")
        return 2

    labeled_rows = []
    for line in labeled.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        labeled_rows.append(row)

    required_labels = ("should_publish", "importance_band", "relevance_band", "is_duplicate")
    unlabeled = [
        row.get("case_id", "unknown")
        for row in labeled_rows
        if any(row.get(key) is None for key in required_labels)
    ]
    print(f"GOLDEN_DATASET records={len(labeled_rows)} unlabeled={len(unlabeled)}")
    if unlabeled:
        print("HISTORICAL_CORPUS_VALIDATION=BLOCKED_INCOMPLETE_GOLD_LABELS")
        return 3

    print("HISTORICAL_CORPUS_VALIDATION=READY_FOR_COMPARATIVE_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
