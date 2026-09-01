"""Fail-closed recovery for the independent Education product stream.

The news pipeline must never be rerun just because Education was deferred. This
small post-run guard checks the authoritative cadence state and, when an
Education slot is still due, invokes the existing independent publisher once.
A confirmed recovery also records the slot so the same lesson cannot be
republished repeatedly within the same Tehran window.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import educational_content
import production_entrypoint
import production_resilient_runner


LESSON_41_CURRENT_SOURCES = [
    {
        "name": "Anthropic: Demystifying evals for AI agents",
        "url": "https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents",
        "year": 2026,
    },
    {
        "name": "OpenAI Academy: Workspace agents",
        "url": "https://openai.com/academy/workspace-agents/",
        "year": 2026,
    },
    {
        "name": "Anthropic: Trustworthy agents in practice",
        "url": "https://www.anthropic.com/research/trustworthy-agents",
        "year": 2026,
    },
]

_ORIGINAL_SOURCE_CANDIDATES = educational_content._source_candidates


def _source_candidates_with_lesson_41_fallback(lesson: dict):
    candidates = _ORIGINAL_SOURCE_CANDIDATES(lesson)
    lesson_id = int(lesson.get("id", 0) or 0)
    if lesson_id != 41:
        return candidates

    stale_urls = {
        "https://www.anthropic.com/research/building-effective-agents",
        "https://platform.openai.com/docs/guides/agents",
    }
    filtered = [
        item for item in candidates
        if str(item.get("url", "")).rstrip("/") not in {u.rstrip("/") for u in stale_urls}
    ]
    filtered.extend(LESSON_41_CURRENT_SOURCES)
    print("[Education Recovery] lesson=41 current-source fallback enabled", flush=True)
    return filtered


def main() -> int:
    educational_content._source_candidates = _source_candidates_with_lesson_41_fallback

    cadence = production_entrypoint._load_cadence()
    due, slot = production_entrypoint._education_is_due(
        production_entrypoint._tehran_now(),
        cadence.get("last_education_slot", ""),
    )

    print(
        f"[Education Recovery] due={due} slot={slot} "
        f"last_slot={cadence.get('last_education_slot', '')} "
        f"last_run={cadence.get('last_education_run', 0)}",
        flush=True,
    )

    if not due:
        print("[Education Recovery] no recovery required", flush=True)
        return 0

    run_number = int(cadence.get("run_number", 0) or 0)
    ok = production_resilient_runner._publish_education_after_news(run_number)
    if not ok:
        print(
            f"[Education Recovery] FAILED slot={slot}; Education remains due",
            flush=True,
        )
        return 1

    cadence = production_entrypoint._load_cadence()
    cadence["last_education_slot"] = slot or cadence.get("last_education_slot", "")
    cadence["last_education_run"] = run_number
    production_entrypoint._save_cadence(cadence)
    print(
        f"[Education Recovery] CONFIRMED slot={slot} run={run_number}; "
        "slot marked complete",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
