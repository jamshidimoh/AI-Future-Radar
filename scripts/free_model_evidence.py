"""Compatibility import shim for scripts executed directly from scripts/."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from free_model_evidence import *  # noqa: F401,F403,E402
