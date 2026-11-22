"""Persistent health classification for unusable model responses."""

from scripts.update_llm_health_state import MODEL_COOLDOWN, classify


def test_empty_model_content_is_a_persisted_model_failure():
    assert classify("LLM response has no content") == "invalid_response"
    assert classify("LLM response content not found") == "invalid_response"
    assert classify("LLM response has no choices") == "invalid_response"
    assert MODEL_COOLDOWN["invalid_response"] >= 3600.0
