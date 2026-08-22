"""Profile the annotation-ready Golden Dataset seed without inventing labels."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    content_types = Counter(str(row.get("expected_content_type") or "unknown") for row in rows)
    leaders = Counter(str(row.get("leader_name")) for row in rows if row.get("leader_name"))
    sources = Counter(
        str(row.get("best_source") or "unknown")
        for row in rows
    )
    return {
        "records": len(rows),
        "annotated_should_publish": sum(row.get("should_publish") is not None for row in rows),
        "annotated_importance": sum(row.get("importance_band") is not None for row in rows),
        "leader_metadata": sum(row.get("leader_name") is not None for row in rows),
        "content_types": dict(content_types),
        "leaders_top": dict(leaders.most_common(15)),
        "sources_top": dict(sources.most_common(15)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile an annotation-ready Radar Golden Dataset seed.")
    parser.add_argument("input", nargs="?", default="data/golden_dataset_seed.jsonl")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"Seed file not found: {path}. Run build_golden_seed.py first.")
    result = profile(load_jsonl(path))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
