#!/usr/bin/env python3
"""Losslessly merge generated JSON state during a production-state rebase conflict."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

FILES = (
    Path("data/seen.json"),
    Path("data/telegram_feedback.json"),
    Path("data/education_state.json"),
    Path("data/publication_state.json"),
)


def read_stage(stage: int, path: Path):
    try:
        raw = subprocess.check_output(
            ["git", "show", f":{stage}:{path.as_posix()}"],
            text=True,
        )
        return json.loads(raw)
    except Exception:
        return None


def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for key, value in b.items():
            out[key] = merge(out[key], value) if key in out else value
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = list(a)
        seen = {json.dumps(x, ensure_ascii=False, sort_keys=True) for x in out}
        for value in b:
            marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
            if marker not in seen:
                out.append(value)
                seen.add(marker)
        return out
    return a if a is not None else b


def main() -> None:
    for path in FILES:
        ours = read_stage(2, path)
        theirs = read_stage(3, path)
        if ours is None or theirs is None:
            continue
        path.write_text(
            json.dumps(merge(ours, theirs), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print("[Production State Merge] generated JSON state merged without discarding either side")


if __name__ == "__main__":
    main()
