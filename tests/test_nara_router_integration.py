from pathlib import Path

from scripts.update_llm_health_state import _iter_events, classify as classify_persisted_health
import src.free_model_registry as registry
import src.llm_router_light as router
from src.production_router_policy import _is_provider_auth, _is_provider_quota

ROOT = Path(__file__).resolve().parents[1]


def test_nara_is_independent_fallback(monkeypatch):
    monkeypatch.setenv("NARAROUTER_API_KEY", "test-nara")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.delenv("KIRAAI_API_KEY", raising=False)
    names = [name for name, _ in registry.build_production_chain(router)]
    assert any(name.startswith("NaraRouter:") for name in names)


def test_nara_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("NARAROUTER_API_KEY", "test-nara")
    seen = {}

    class Response:
        status_code = 200
        text = '{"ok":true}'

        def json(self):
            return {"model": "auto/bynara", "choices": [{"message": {"content": '{"ok":true}'}}]}

        def raise_for_status(self):
            return None

    def post(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr(router.requests, "post", post)
    assert router._nara("system", "user", "auto/bynara") == '{"ok":true}'
    assert seen["url"] == "https://router.bynara.id/v1/chat/completions"


def test_json_generation_failure_does_not_disable_provider():
    message = "Failed to generate JSON. failed_generation=max completion tokens reached"
    assert not _is_provider_auth(message)
    assert not _is_provider_quota(message)



def test_nara_telegram_required_is_provider_level_auth_failure():
    message = (
        "NaraRouter auto/bynara: HTTP 403 "
        "{'type':'forbidden','message':'telegram_required: Join the required "
        "Telegram group/channel and relink at /settings to continue.'}"
    )
    assert _is_provider_auth(message)


def test_nara_telegram_required_is_persisted_as_provider_auth_not_model_error():
    # This is the real production log shape from the HTTP 403 failure. The
    # health-state parser must prioritize the account-linking marker over 403.
    line = (
        '[Production Circuit] failed=nararouter:auto/bynara reason=auth scope=provider: '
        'exception=QuotaExceeded provider=nararouter model=nararouter:auto/bynara '
        'NaraRouter auto/bynara: HTTP 403 '
        '{"error":{"type":"forbidden","message":"telegram_required: Join the required '
        'Telegram group/channel and relink at /settings to continue."}}'
    )
    assert classify_persisted_health(line) == "auth"
    events = list(_iter_events([line]))
    assert events == [("nararouter:auto/bynara", "failure", "auth", False)]


def test_nara_model_permission_403_is_not_misclassified_as_provider_auth():
    message = "Groq qwen/qwen3.6-27b: HTTP 403 model_permission_blocked_project"
    assert not _is_provider_auth(message)
