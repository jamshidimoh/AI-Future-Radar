"""Shared test isolation for persisted production health state."""


import pytest


@pytest.fixture(autouse=True)
def isolate_persisted_llm_health(monkeypatch):
    """Keep registry-order tests independent from repository health history."""
    import src.free_model_service as service
    from src.free_model_service import FreeModelIntelligence

    monkeypatch.setattr(service, "_DEFAULT_INTELLIGENCE", FreeModelIntelligence(persist=False))
    yield
