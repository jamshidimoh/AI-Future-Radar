"""Generate deterministic characterization fixtures on the current selector contract."""
from __future__ import annotations

import json
import random
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.semantic_dedup import _similarity  # noqa: E402
from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio  # noqa: E402

OUT = Path(__file__).resolve().parent
SEED = 20260913


def _semantic_fixture() -> dict:
    titles = [
        "OpenAI raises $6.6B to scale frontier reasoning models",
        "OpenAI secures $6.6B funding for new reasoning systems",
        "Nvidia CEO Jensen Huang says AI factories will reshape computing",
        "جنسن هوانگ مدیرعامل انویدیا از کارخانه‌های هوش مصنوعی می‌گوید",
        "Anthropic appoints new CFO amid rapid enterprise growth",
        "Anthropic names a new finance chief during expansion",
        "Google DeepMind unveils a robotics foundation model",
