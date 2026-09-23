from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'run.yml'


def test_omniroute_workflow_uses_audited_release_and_provider_ids():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'omniroute@3.8.51' in text
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
    assert 'no provider inference smoke-test executed; quota is preserved' in text

# Production validation trigger: OmniRoute 3.8.51 contract.
