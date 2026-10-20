# ruff: noqa: I001
import pathlib


WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'run.yml'


def test_omniroute_workflow_uses_audited_release_and_provider_ids():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'OMNIROUTE_VERSION=3.8.50' in text
    assert 'OMNIROUTE_COMMIT=5458026c216f77a3da68ea49152dc33470cfe2cb' in text
    assert 'git clone --depth 1 --branch "v${OMNIROUTE_VERSION}" https://github.com/diegosouzapw/OmniRoute.git' in text
    assert 'HUSKY=0 timeout 420s npm ci --include=dev --no-audit' in text
    assert 'npm ci --omit=dev' not in text
    assert 'npm install -g omniroute@' not in text
    assert 'framer-motion@14.3.1' in text
    assert 'add_provider gemini GEMINI_API_KEY' not in text
    assert 'add_provider google GEMINI_API_KEY' not in text
    assert 'OMNIROUTE_ENABLE_NARA: ${{ vars.OMNIROUTE_ENABLE_NARA || \'0\' }}' in text
    assert 'if [ "${OMNIROUTE_ENABLE_NARA:-0}" = "1" ]; then' in text
    assert 'add_provider nara NARAROUTER_API_KEY' in text
    assert 'nara: deferred from auto-pool until the account Telegram gate is resolved' in text

    for provider, credential in (
        ('groq', 'GROQ_API_KEY'),
        ('huggingface', 'HF_TOKEN'),
        ('mistral', 'MISTRAL_API_KEY'),
        ('llm7', 'LLM7_API_KEY'),
        ('nvidia', 'NVIDIA_API_KEY'),
        ('anyapi', 'ANYAPI_API_KEY'),
        ('api-airforce', 'API_AIRFORCE_API_KEY'),
        ('sambanova', 'SAMBANOVA_API_KEY'),
    ):
        assert f'add_provider {provider} {credential}' in text

    assert 'cloudflare-ai: deferred (requires accountId in provider-specific connection data)' in text
    assert 'CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}' in text
    assert 'OMNIROUTE_READY' in text
    assert 'providers test-all' not in text
    assert '[OmniRoute] running minimal auto/smart inference smoke-test' in text
    assert '\"model\":\"auto/smart\"' in text

# Production validation trigger: pinned OmniRoute source tag and lockfile contract.

# Final production validation: secrets + OmniRoute + TypeSafe.



def test_ollama_and_gemini_are_not_configured_as_providers():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "ollama.com/install.sh" not in text
    assert "RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK" not in text
    assert "RADAR_ENABLE_GEMINI_FALLBACK" not in text
    assert "GEMINI_API_KEY" not in text
    assert 'if [ "${OMNIROUTE_READY:-0}" = "1" ]; then' in text
    assert 'export OMNIROUTE_BASE_URL="http://127.0.0.1:20128"' in text
    assert "unset OMNIROUTE_BASE_URL" in text


def test_omniroute_bootstrap_has_hard_timeouts_and_fallback_safe_probes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    start = workflow.index("      - name: Install and start ephemeral OmniRoute")
    end = workflow.index("      - name: Install dependencies", start)
    step = workflow[start:end]
    assert "timeout-minutes: 40" in step
    assert 'timeout 60s git clone --depth 1 --branch "v${OMNIROUTE_VERSION}"' in step
    assert "HUSKY=0 timeout 420s npm ci --include=dev --no-audit" in step
    assert 'node-version: "24"' in text
    assert "timeout 720s npm run build:backend" in step
    assert "backend-only production build timed out or failed" in step
    assert "nohup npm run start > /tmp/omniroute.log 2>&1 &" in step
    assert "nohup omniroute > /tmp/omniroute.log" not in step
    assert 'test "$(git rev-parse HEAD)" = "$OMNIROUTE_COMMIT"' in step
    assert "OMNIROUTE_READY=0" in step
    assert "OMNIROUTE_READY_LOCAL=1" in step
    assert "timeout 10s omniroute --version" in step
    assert "timeout 15s omniroute providers list --json" in step
    assert "timeout 20s omniroute providers validate" in step
    assert "--connect-timeout 3 --max-time 10 http://127.0.0.1:20128/v1/models" in step
    assert "continuing with fallback" in step



def test_omniroute_result_provider_preserves_upstream_family_for_independent_retry():
    import src.llm_router_light as router
    from src.production_router_policy import _omniroute_result_provider

    provider = _omniroute_result_provider(
        "qwen/qwen3.8-27b",
        "strategy=auto; provider=groq; latency_ms=809",
    )

    assert provider == "Groq:qwen/qwen3.8-27b"
    assert router._provider_family(provider) == "groq"


def test_omniroute_result_provider_handles_mistral_and_whitespace_in_decision_metadata():
    from src.production_router_policy import _omniroute_result_provider

    assert _omniroute_result_provider(
        "codestral-2508",
        "strategy=auto; provider = mistral; latency_ms=2773",
    ) == "Mistral:codestral-2508"


def test_omniroute_result_provider_does_not_guess_without_decision_metadata():
    from src.production_router_policy import _omniroute_result_provider

    assert _omniroute_result_provider("qwen/qwen3.8-27b", "") == "OmniRoute:qwen/qwen3.8-27b"


def test_omniroute_call_returns_upstream_family_from_decision_header(monkeypatch):
    import src.production_router_policy as policy
    import src.llm_router_light as router

    class FakeResponse:
        status_code = 200
        text = ""
        headers = {
            "X-OmniRoute-Decision": "strategy=auto; provider=groq; latency_ms=809",
        }

        @staticmethod
        def json():
            return {
                "model": "qwen/qwen3.8-27b",
                "choices": [{"message": {"content": '{"title":"ok"}'}}],
            }

    monkeypatch.setenv("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128")
    monkeypatch.setenv("OMNIROUTE_API_KEY", "")
    monkeypatch.setattr(policy.requests, "post", lambda *args, **kwargs: FakeResponse())

    content, provider = policy._omniroute_call("system", "user")

    assert content == '{"title":"ok"}'
    assert provider == "Groq:qwen/qwen3.8-27b"
    assert router._provider_family(provider) == "groq"
