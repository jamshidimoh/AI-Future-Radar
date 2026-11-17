# Free-tier LLM routing policy

This production workflow is designed to consume provider-published free allowances without silently switching to a paid tier after a free quota is exhausted.

## Routing rules

- **OpenRouter:** Always provision the OpenRouter connection, but the direct Radar fallback accepts only model IDs ending in `:free`. Before each direct request, it reads `free_model_daily_requests.remaining` from `GET /api/v1/key`, reserves one request locally, enforces the published 20 requests/minute ceiling, and fails closed when the counter cannot be read. The free-model daily allowance is shared across free variants and failed attempts count against it. Do not replace a `:free` model ID with a zero-price non-`:free` model: OpenRouter states that some other $0 models still require a funded account.
- **Groq:** Enabled only when the repository Actions variable `GROQ_FREE_TIER_CONFIRMED=1` is set. The account must remain on Groq Free with no payment method attached. Per-model RPM/RPD/TPM/TPD response limits are honored; model-specific exhaustion cools down only that model and the cooldown follows the provider reset rather than disabling sibling models.
- **SambaNova:** Enabled only when `SAMBANOVA_FREE_TIER_CONFIRMED=1` is set. The account must have no payment method linked, which is the documented condition for SambaNova Free Tier. The current production models have a 20 RPM, 20 RPD, and 200,000 TPD allowance per model. The provider's response headers are the source of current remaining/reset values.
- **API.Airforce:** Enabled only when `API_AIRFORCE_FREE_TIER_CONFIRMED=1` is set. The account must be on its Free plan and have zero Pay-as-you-go wallet balance; a positive PayGo balance bypasses the Free request limits. The Free plan's published cap is 1 RPM and 1,000 RPD.

All three opt-in variables default to `0`. The corresponding API key is not passed to the inference process unless its variable is exactly `1`. Set a variable only after checking the provider account itself; the workflow cannot infer whether an externally stored API key has a linked payment method or funded wallet.

## Provider reset behavior

Quota exhaustion is not treated as a generic provider outage. The router distinguishes:
- per-model quotas from account-wide or API-key-wide quotas;
- minute windows from daily windows;
- temporary shared-pool 429s from a provider's own exhausted free allowance.

It persists the reset instant and skips the affected model or account until that time. A recovery attempt does not clear an unexpired quota cooldown. OpenRouter's daily cap blocks all sibling `:free` models for the same account; a model-specific upstream shared-pool 429 does not block the entire OpenRouter account.

Unknown quota, missing quota telemetry, missing credentials, or an account that has not been verified as Free is not treated as permission to spend. It is excluded or fails closed.

## Providers deliberately not in the automatic production pool

- **Mistral:** Current Mistral plan documentation says Free mode does not include API access; API keys/API use require billing activation.
- **NVIDIA API:** Free access is restricted to prototyping, development, research, or evaluation, so it is not part of the production pool.
- **LLM7 and AnyAPI:** Not admitted to this production route until their production eligibility and account-level no-billing cutoff can be verified.
- **Cloudflare Workers AI:** Requires an account-specific plan check and a confirmed free-plan cap; it is not currently wired into the provisioned OmniRoute connection.
- **NaraRouter and KiraAI:** Remain disabled in the automatic pool while their account-linking/wallet conditions are unresolved.
- **Hugging Face:** Monthly inference credits are not treated as a guaranteed recurring hard-stop free allowance.

## Required GitHub Actions variables

In **Repository Settings → Secrets and variables → Actions → Variables**, set a variable to `1` only after confirming the stated condition:

| Variable | Required account condition |
|---|---|
| `GROQ_FREE_TIER_CONFIRMED` | Groq Free plan; no payment method linked |
| `SAMBANOVA_FREE_TIER_CONFIRMED` | SambaNova account has no payment method linked |
| `API_AIRFORCE_FREE_TIER_CONFIRMED` | API.Airforce Free plan; PayGo balance is zero |

The API keys remain repository Actions secrets:
`GROQ_API_KEY`, `SAMBANOVA_API_KEY`, and `API_AIRFORCE_API_KEY`.

## Official references

- OpenRouter free models and rate limits: https://openrouter.ai/collections/free-models/
- OpenRouter key usage endpoint: https://openrouter.ai/docs/api-reference/api-keys/get-current-key
- Groq rate limits: https://console.groq.com/docs/rate-limits
- Groq billing and Free-to-Developer upgrade: https://console.groq.com/docs/billing-faqs
- SambaNova rate limits and Free Tier eligibility: https://docs.sambanova.ai/docs/en/models/rate-limits
- API.Airforce Free-plan request limits: https://api.airforce/docs/quickstart/
- API.Airforce PayGo and billing behavior: https://api.airforce/docs/billing/
- Mistral plan and API access: https://docs.mistral.ai/admin/billing-usage/usage-limits
