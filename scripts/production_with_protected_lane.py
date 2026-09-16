"""Canonical production launcher.

The production entrypoint owns both publication lanes. This module remains only
as the workflow-compatible launcher and resilience boundary.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import production_resilient_runner  # noqa: E402, I001


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
