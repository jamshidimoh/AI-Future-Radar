import importlib
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def test_src_modules_have_single_identity():
    names = sorted(p.stem for p in SRC.glob("*.py") if p.stem != "__init__")
    for name in names:
        importlib.import_module(f"src.{name}")
    leaked = [n for n in names if n in sys.modules]
    assert leaked == []
