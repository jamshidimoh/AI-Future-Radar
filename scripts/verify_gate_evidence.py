from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: verify_gate_evidence.py <gate> <commit_sha> <workflow_run_id>")
    gate, commit_sha, workflow_run_id = sys.argv[1:]
    path = Path("evolution/gate_evidence.jsonl")
    if not path.exists():
        raise SystemExit("evidence ledger missing")
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("{") and '"note"' in raw:
            continue
        record = json.loads(raw)
        if (
            record.get("gate") == gate
            and record.get("commit_sha") == commit_sha
            and str(record.get("workflow_run_id")) == workflow_run_id
            and record.get("test_result") == "PASS"
            and record.get("acceptance_result") == "PASS"
        ):
            print("VALID_GATE_EVIDENCE")
            return 0
    raise SystemExit("no matching PASS evidence for exact gate/commit/run")


if __name__ == "__main__":
    raise SystemExit(main())
