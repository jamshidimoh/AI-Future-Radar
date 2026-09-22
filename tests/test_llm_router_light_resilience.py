from pathlib import Path

from src.llm_router_light import _failure_class, _provider_timeout, _should_disable_provider

ROOT = Path(__file__).resolve().parents[1]


def test_unavailable_provider_codes_are_disabled():
    assert _should_disable_provider("404 Client Error: Not Found")
    assert _should_disable_provider("HTTP 401 unauthorized")
    assert _should_disable_provider("HTTP 403 forbidden")
    assert _should_disable_provider("HTTP 503 service unavailable")


def test_transient_non_provider_error_is_not_permanently_disabled():
    assert not _should_disable_provider("connection reset by peer")
    assert not _should_disable_provider("JSON decode failed")


def test_provider_timeout_is_bounded_by_provider_class_and_remaining_budget():
    assert _provider_timeout("Groq:qwen/qwen3.6-27b", 20) == 8.0
    assert _provider_timeout("OpenRouter:test:free", 20) == 7.0
    assert _provider_timeout("Gemini", 20) == 8.0
    assert _provider_timeout("Groq:qwen/qwen3.6-27b", 3) == 3.0


def test_unknown_provider_has_safe_default_timeout():
    assert _provider_timeout("Unknown", 20) == 4.0


def test_no_deployments_is_treated_as_transient_exhaustion():
    assert _failure_class("No deployments available for selected model") == "transient"
