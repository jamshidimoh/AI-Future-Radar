"""Fail-closed JSON state loading."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StateCorruptionError(RuntimeError):
    """Raised when persisted JSON state cannot be read safely."""


def load_json_state(path: str | Path, default: Any, *, label: str) -> Any:
    """Return ``default`` for a missing state file; reject unreadable state."""
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StateCorruptionError(f"{label} at {path} is unreadable: {exc}") from exc
