"""Shared test isolation for persisted production health state."""


import pytest


@pytest.fixture(autouse=True)
def isolate_publication_guard(monkeypatch, tmp_path):
    """Keep publication-history checks independent across tests."""
    from src import publication_guard

    ledger = tmp_path / "telegram_feedback.json"
    ledger.write_text('{"version": 2, "messages": {}}', encoding="utf-8")
    monkeypatch.setattr(publication_guard, "LEDGER_PATH", ledger)


@pytest.fixture(autouse=True)
def isolate_persisted_llm_health(monkeypatch):
    """Keep registry-order tests independent from repository health history."""
    import src.free_model_service as service
    from src.free_model_service import FreeModelIntelligence

    monkeypatch.setattr(service, "_DEFAULT_INTELLIGENCE", FreeModelIntelligence(persist=False))
    yield
