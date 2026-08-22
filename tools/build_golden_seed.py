"""Build an annotation-ready Golden Dataset seed from historical Telegram feedback.

This tool deliberately does NOT claim the resulting records are a labeled Golden
Dataset. Historical feedback contains publication metadata, but not reliable
reject/importance/relevance labels. The output is therefore an annotation queue
that can be reviewed and promoted into the acceptance benchmark.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "case_id",
    "source_items",
    "canonical_story_id",
    "should_publish",
    "importance_band",
    "relevance_band",
    "best_source",
    "expected_story_group",
    "is_duplicate",
    "leader_name",
    "leader_relevance",
    "is_substantive_interview",
    "is_model_release",
    "risk_level",
    "minimum_evidence_level",
    "expected_rank_band",
    "expected_content_type",
    "notes",
)


def _record_key(message: dict[str, Any]) -> str:
    return str(message.get("link") or f"{message.get('chat_id')}:{message.get('message_id')}").strip()


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _recency_key(message: dict[str, Any]) -> tuple[int, int]:
    """Return a deterministic chronological key for historical messages."""
    return (_integer(message.get("posted_at")), _integer(message.get("message_id")))


def build_seed(feedback: dict[str, Any], limit: int = 200) -> list[dict[str, Any]]:
    messages = feedback.get("messages", {})
    unique: dict[str, dict[str, Any]] = {}
    for value in messages.values():
        if not isinstance(value, dict):
            continue
        key = _record_key(value)
        if not key:
            continue

        # Keep the newest metadata for an exact record/link while preserving
        # deterministic chronological ordering of the resulting seed.
        previous = unique.get(key)
        if previous is None or _recency_key(value) >= _recency_key(previous):
            unique[key] = value

    # Annotation queues are chronological: older cases receive stable low IDs,
    # and exact-link duplicates contribute their latest historical metadata.
    ordered = sorted(unique.values(), key=_recency_key)

    result: list[dict[str, Any]] = []
    for index, message in enumerate(ordered[: max(0, limit)], start=1):
        url = str(message.get("link") or "").strip()
        title = str(message.get("title") or "").strip()
        source = str(message.get("source") or "").strip()
        content_type = str(message.get("content_type") or "news").strip()
        leader = str(message.get("leader") or message.get("watch_person") or "").strip() or None
        result.append(
            {
                "case_id": f"hist-{index:04d}",
                "source_items": [
                    {
                        "source_id": source,
                        "source_name": source,
                        "url": url,
                        "title": title,
                        "content_type": content_type,
                        "published_at": message.get("posted_at"),
                        "leader": leader,
                    }
                ],
                "canonical_story_id": None,
                "should_publish": None,
                "importance_band": None,
                "relevance_band": None,
                "best_source": source or None,
                "expected_story_group": None,
                "is_duplicate": None,
                "leader_name": leader,
                "leader_relevance": None,
                "is_substantive_interview": content_type in {"interview", "podcast", "talk"},
                "is_model_release": None,
                "risk_level": None,
                "minimum_evidence_level": None,
                "expected_rank_band": None,
                "expected_content_type": content_type,
                "notes": "Historical published item; human annotation required before acceptance use.",
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an annotation-ready Golden Dataset seed.")
    parser.add_argument("--input", default="data/telegram_feedback.json")
    parser.add_argument("--output", default="data/golden_dataset_seed.jsonl")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    feedback = json.loads(input_path.read_text(encoding="utf-8"))
    records = build_seed(feedback, limit=args.limit)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"GOLDEN_SEED_CREATED records={len(records)} output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
