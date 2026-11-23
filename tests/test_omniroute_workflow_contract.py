# ruff: noqa: I001
import pathlib


WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'run.yml'


def test_omniroute_workflow_uses_audited_release_and_only_verified_free_providers():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "OMNIROUTE_VERSION=3.8.50" in workflow
    assert "OMNIROUTE_COMMIT=5458026c216f77a3da68ea49152dc33470cfe2cb" in workflow
    assert 'git clone --depth 1 --branch "v${OMNIROUTE_VERSION}" https://github.com/diegosouzapw/OmniRoute.git' in workflow
    assert "HUSKY=0 timeout 180s npm install --package-lock-only --ignore-scripts --include=dev --no-audit --no-fund --prefer-offline --no-progress" in workflow
    assert "HUSKY=0 timeout 420s npm ci --include=dev --no-audit" in workflow
    assert workflow.index("npm install --package-lock-only --ignore-scripts --include=dev") < workflow.index("npm ci --include=dev")
    assert "npm ci --omit=dev" not in workflow
    assert "npm install -g omniroute@" not in workflow
    assert "brace-expansion@1.1.21" in workflow

    assert "add_provider gemini GEMINI_API_KEY" not in workflow
    assert "add_provider google GEMINI_API_KEY" not in workflow
    assert "add_provider nara NARAROUTER_API_KEY" not in workflow
    assert "add_provider mistral MISTRAL_API_KEY" not in workflow
    assert "add_provider nvidia NVIDIA_API_KEY" not in workflow
    assert "add_provider llm7 LLM7_API_KEY" not in workflow
    assert "add_provider anyapi ANYAPI_API_KEY" not in workflow
    assert "add_provider huggingface HF_TOKEN" not in workflow
    assert "add_provider nara NARAROUTER_API_KEY" not in workflow

    assert 'add_provider openrouter OPENROUTER_API_KEY' in workflow
    assert 'add_provider groq GROQ_API_KEY' in workflow
    assert 'add_provider sambanova SAMBANOVA_API_KEY' in workflow
    assert 'add_provider api-airforce API_AIRFORCE_API_KEY' in workflow
    assert "GROQ_FREE_TIER_CONFIRMED" in workflow
    assert "SAMBANOVA_FREE_TIER_CONFIRMED" in workflow
    assert "API_AIRFORCE_FREE_TIER_CONFIRMED" in workflow
    assert "Free tier/no payment method verified" in workflow
    assert "no payment method linked" in workflow
    assert "zero PayGo balance verified" in workflow
    assert "vars.GROQ_FREE_TIER_CONFIRMED == '1' && secrets.GROQ_API_KEY" in workflow
    assert "vars.SAMBANOVA_FREE_TIER_CONFIRMED == '1' && secrets.SAMBANOVA_API_KEY" in workflow
    assert "vars.API_AIRFORCE_FREE_TIER_CONFIRMED == '1' && secrets.API_AIRFORCE_API_KEY" in workflow
    assert 'OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}' in workflow
    assert "auto/best-free" in workflow
    assert "Mistral Free mode has no API access" in workflow
    assert "NVIDIA hosted API is limited to" in workflow
    assert "LLM7 is not a managed production inference service" in workflow
    assert "Cloudflare" in workflow
    assert "OMNIROUTE_READY" in workflow
    assert "providers test-all" not in workflow
    assert '"POST", endpoint' in workflow
    assert "/api/providers/{provider_id}/sync-models?mode=sync&quiet=1" in workflow
    assert "model_sync_total" in workflow
    assert "waiting for the synchronized model catalog" in workflow
    assert '{"openrouter", "groq", "sambanova", "api-airforce"}' in workflow
    assert "[OmniRoute] running structured auto/best-free inference smoke-test" in workflow
    assert "[OmniRoute] structured_json_inference_smoke=healthy" in workflow
    assert '"response_format":{"type":"json_object"}' in workflow
    assert '"max_tokens":128' in workflow
    assert 'result.get("ok") is True' in workflow
    assert '"model":"auto/best-free"' in workflow

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
    assert "HUSKY=0 timeout 180s npm install --package-lock-only --ignore-scripts --include=dev --no-audit --no-fund --prefer-offline --no-progress" in step
    assert "HUSKY=0 timeout 420s npm ci --include=dev --no-audit" in step
    assert step.index("npm install --package-lock-only --ignore-scripts --include=dev") < step.index("npm ci --include=dev")
    assert 'node-version: "24"' in workflow
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
    assert '[OmniRoute] structured_json_inference_smoke=healthy' in step
    assert '"response_format":{"type":"json_object"}' in step
    assert '"max_tokens":128' in step



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

def test_empty_omniroute_catalog_fails_closed_before_inference_smoke():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    guard = 'if [ "${MODEL_COUNT:-0}" -le 0 ]; then'
    smoke = 'echo "[OmniRoute] running structured auto/best-free inference smoke-test"'

    assert guard in workflow
    assert smoke in workflow
    guard_start = workflow.index(guard)
    smoke_start = workflow.index(smoke)
    assert guard_start < smoke_start

    guard_block = workflow[guard_start:smoke_start]
    assert 'echo "OMNIROUTE_READY=0" >> "$GITHUB_ENV"' in guard_block
    assert 'echo "[OmniRoute] ready=0"' in guard_block
    assert "exit 0" in guard_block


def test_cloudflare_workers_ai_is_gated_and_passed_to_direct_production_steps():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    token_binding = "CLOUDFLARE_API_TOKEN: ${{ vars.CLOUDFLARE_FREE_TIER_CONFIRMED == '1' && secrets.CLOUDFLARE_API_TOKEN || '' }}"
    account_binding = "CLOUDFLARE_ACCOUNT_ID: ${{ vars.CLOUDFLARE_FREE_TIER_CONFIRMED == '1' && vars.CLOUDFLARE_ACCOUNT_ID || '' }}"
    assert workflow.count(token_binding) == 3
    assert workflow.count(account_binding) == 3
    assert "Cloudflare Workers AI is" in workflow
    assert "add_provider cloudflare-ai" not in workflow
