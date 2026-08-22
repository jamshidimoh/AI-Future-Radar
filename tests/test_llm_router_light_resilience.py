import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_router_light import _provider_timeout, _should_disable_provider


def test_unavailable_provider_codes_are_disabled():
    assert _should_disable_provider("404 Client Error: Not Found")
    assert _should_disable_provider("HTTP 401 unauthorized")
    assert _should_disable_provider("HTTP 403 forbidden")
    assert _should_disable_provider("HTTP 503 service unavailable")


def test_transient_non_provider_error_is_not_permanently_disabled():
    assert not _should_disable_provider("connection reset by peer")
    assert not _should_disable_provider("JSON decode failed")


def test_provider_timeout_is_bounded_by_provider_class_and_remaining_budget():
    assert _provider_timeout("Groq:qwen/qwen3.6-27b", 20) == 6.0
    assert _provider_timeout("OpenRouter:test:free", 20) == 2.5
    assert _provider_timeout("Gemini", 20) == 10.0
    assert _provider_timeout("Groq:qwen/qwen3.6-27b", 3) == 3.0


def test_unknown_provider_has_safe_default_timeout():
    assert _provider_timeout("Unknown", 20) == 4.0
