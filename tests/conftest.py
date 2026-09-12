"""Shared test isolation for persisted production health state."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
src_dir = str(ROOT / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


@pytest.fixture(autouse=True)
def isolate_persisted_llm_health(monkeypatch):
    """Keep registry-order tests independent from repository health history."""
    import free_model_service as service
    from free_model_service import FreeModelIntelligence

    monkeypatch.setattr(service, "_DEFAULT_INTELLIGENCE", FreeModelIntelligence(persist=False))
    yield
