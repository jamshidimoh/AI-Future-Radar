# Free inference provider setup

The production router supports independent Groq and Cloudflare Workers AI lanes. OpenRouter remains a lower-priority backup. Provider credentials are never committed to the repository.

## 1. Groq Free

1. Create an API key in the [Groq Console](https://console.groq.com/keys).
2. Confirm the account is still on the Free plan in the Groq Console. Do not upgrade to Developer or enter a paid billing flow for this configuration.
3. In GitHub, open **Settings → Secrets and variables → Actions**:
   - Add repository secret `GROQ_API_KEY`.
   - Add repository variable `GROQ_FREE_TIER_CONFIRMED` with value `1`.

Groq's free limits vary by model and are enforced per organization. Check the live limits and usage shown by the [official rate-limit documentation](https://console.groq.com/docs/rate-limits) before relying on a model for a scheduled run. The router treats Groq model quota errors as model-scoped so another Groq model can still be tried.

## 2. Cloudflare Workers AI Free

1. Keep the Cloudflare account on **Workers Free**. Do not upgrade to Workers Paid and do not attach prepaid AI Gateway credits for this free-only configuration.
2. Open the [Workers AI dashboard](https://dash.cloudflare.com/?to=/:account/workers-ai) and create a Workers AI API token. When creating a custom token, grant only the account-scoped **Workers AI Read** and **Workers AI Edit** permissions required by the REST API.
3. Copy the account ID shown on the Workers AI page.
4. In GitHub **Settings → Secrets and variables → Actions**:
   - Add repository secret `CLOUDFLARE_API_TOKEN`.
   - Add repository variable `CLOUDFLARE_ACCOUNT_ID`.
   - Add repository variable `CLOUDFLARE_FREE_TIER_CONFIRMED` with value `1`.

The adapter uses the OpenAI-compatible Workers AI endpoint and registers two active JSON Mode models: `@cf/meta/llama-3.3-70b-instruct-fp8-fast` and the lighter `@cf/meta/llama-3.1-8b-instruct-fast`. Cloudflare's changelog confirms the fast 8B variant remains active; the non-fast Llama 3.1 8B model was deprecated and is deliberately excluded. The router checks for both the token and account ID; the workflow passes either value to production only when `CLOUDFLARE_FREE_TIER_CONFIRMED=1`.

Cloudflare documents a **10,000 Neurons/day** free allocation on Workers Free, resetting at 00:00 UTC. On Workers Free, requests fail after the free allocation is exhausted; Workers Paid can bill usage above the allowance. Therefore, do not set the confirmation variable to `1` on a Paid account. The runtime treats Cloudflare quota exhaustion as account-wide and stops retrying sibling Cloudflare models until the next UTC reset.

Official references:
- [Workers AI REST API setup](https://developers.cloudflare.com/workers-ai/get-started/rest-api/)
- [Workers AI pricing and free allocation](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Workers AI JSON Mode supported models](https://developers.cloudflare.com/workers-ai/features/json-mode/)
- [Cloudflare API token permissions](https://developers.cloudflare.com/fundamentals/api/reference/permissions/)

## 3. Release sequence

After adding the secrets and variables, allow the pull request's CI checks to finish. Do not merge before checking the provider secrets and free-plan confirmation flags: merging this workflow change triggers the production workflow through the repository's `push` event.

The first production run must confirm in its redacted logs that both `Groq` and `Cloudflare-AI` appear in the production model chain and that each completes a structured-JSON smoke/inference request. A configured key or a green CI run alone does not prove the provider is usable. Keep the existing editorial acceptance, duplicate, relevance, and Telegram publication gates unchanged.
