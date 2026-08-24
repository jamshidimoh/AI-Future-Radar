from __future__ import annotations

import inspect

import production_entrypoint


def test_delivery_callback_accepts_source_link():
    source = inspect.getsource(production_entrypoint.main)
    assert 'def delivery_and_capture(text, image_url="", source_link=""):' in source


def test_delivery_callback_uses_publication_orchestrator():
    source = inspect.getsource(production_entrypoint.main)
    assert 'publish_production_story(item, policy=policy, transport=transport, ledger=_ledger)' in source


def test_delivery_callback_preserves_canonical_source_link():
    source = inspect.getsource(production_entrypoint.main)
    assert 'item["link"] = source_link' in source
    assert 'source_link = str(story.get("link") or story.get("url") or "")' in source
