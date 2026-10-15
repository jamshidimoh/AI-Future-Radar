# ruff: noqa: I001
import pathlib


WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'run.yml'


def test_omniroute_workflow_uses_audited_release_and_provider_ids():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'omniroute@3.8.50' in text
    assert 'add_provider gemini GEMINI_API_KEY' in text
    assert 'add_provider google GEMINI_API_KEY' not in text

    for provider, credential in (
        ('groq', 'GROQ_API_KEY'),
        ('huggingface', 'HF_TOKEN'),
        ('nara', 'NARAROUTER_API_KEY'),
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

# Production validation trigger: OmniRoute 3.8.50 contract.

# Final production validation: secrets + OmniRoute + TypeSafe.



def test_local_ollama_fallback_has_cold_start_timeout_for_cpu_inference():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("RADAR_OLLAMA_TIMEOUT_SECONDS: 90") == 2
    assert "RADAR_OLLAMA_FREE_MODEL: qwen3:1.7b" in text



def test_omniroute_bootstrap_has_hard_timeouts_and_fallback_safe_probes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    start = workflow.index("      - name: Install and start ephemeral OmniRoute")
    end = workflow.index("      - name: Install dependencies", start)
    step = workflow[start:end]
    assert "timeout-minutes: 25" in step
    assert "timeout 420s npm install" in step
    assert "timeout 10s omniroute --version" in step
    assert "timeout 15s omniroute providers list --json" in step
    assert "timeout 20s omniroute providers validate" in step
    assert "--connect-timeout 3 --max-time 10 http://127.0.0.1:20128/v1/models" in step
    assert "continuing with fallback" in step
