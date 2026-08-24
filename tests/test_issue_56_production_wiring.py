from pathlib import Path


PRODUCTION_ENTRYPOINT = Path(__file__).resolve().parents[1] / "production_entrypoint.py"


def test_production_entrypoint_uses_canonical_publication_orchestrator():
    source = PRODUCTION_ENTRYPOINT.read_text(encoding="utf-8")
    assert "publish_production_story" in source
    assert "publish_production_story(item" in source
    assert "delivery_result(send(" not in source


def test_production_entrypoint_does_not_register_publication_ledger_before_orchestration():
    source = PRODUCTION_ENTRYPOINT.read_text(encoding="utf-8")
    assert "register_post(store, meta, item)" in source
    assert "ledger=_ledger" in source
    assert "last_delivery[\"outcome\"] = outcome" in source
