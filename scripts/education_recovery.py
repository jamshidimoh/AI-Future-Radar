"""Fail-closed recovery for the independent Education product stream.

The news pipeline must never be rerun just because Education was deferred. This
small post-run guard checks the authoritative cadence state and, when an
Education slot is still due, invokes the existing independent publisher once.
A confirmed recovery also records the slot so the same lesson cannot be
republished repeatedly within the same Tehran window.
"""
from __future__ import annotations

import sys

import production_entrypoint
import production_resilient_runner


def main() -> int:
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
