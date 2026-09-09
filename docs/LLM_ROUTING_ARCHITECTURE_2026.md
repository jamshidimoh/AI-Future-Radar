# AI Future Radar LLM Routing Architecture (2026-09-09)

## Purpose

The LLM layer is a reliability subsystem, not an editorial authority. The editorial pipeline decides which stories deserve publication; the LLM layer transforms evidence into Persian structured drafts and performs only bounded repair.

## Runtime sequence

```text
Current provider metadata
        |
        v
Daily runtime discovery/credential validation
        |
        v
Canonical Trust List (explicit priority)
        |
        v
Capability filter (free/chat/JSON-capable)
        |
        v
Provider/model health state
        |
        v
Priority queue (no random reordering)
        |
        v
Single bounded LLM call per stage + bounded repair
        |
        v
Deterministic language/length/value/grounding gates
        |
        v
Publication policy and Telegram
```

## Trust policy

Production priority is stored explicitly in `config/free_model_registry.yaml`. Runtime discovery may confirm availability, update capabilities, or disable an unavailable entry. It does not silently replace the canonical order.

The current core order is:

1. OpenRouter `nvidia/nemotron-3-ultra-550b-a55b:free`
2. OpenRouter `nvidia/nemotron-3-super-120b-a12b:free`
3. Groq `openai/gpt-oss-120b`
4. Groq `qwen/qwen3.6-27b`
5. OpenRouter `openai/gpt-oss-120b:free`
6. OpenRouter `google/gemma-4-31b-it:free`
7. OpenRouter `qwen/qwen3-next-80b-a3b-instruct:free`
8. OpenRouter `google/gemma-4-26b-a4b-it:free`
9. OpenRouter `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
10. Groq `openai/gpt-oss-20b`
11. OpenRouter `openai/gpt-oss-20b:free`

`Nemotron 3 Nano 30B A3B` was removed from the trust list because its OpenRouter page announced it was going away on August 24, 2026. `Nemotron 3 Nano Omni` is the current free Nemotron small-model replacement in the registry.

`qwen/qwen3.8-27b` is not a trusted production priority. Even though Groq currently lists it among free-plan rate-limit entries, historical project behavior and the agreed trust policy make it a discovery-only candidate rather than a ranking leader.

## Capability policy

Structured JSON is a capability, not a transport assumption. Models that support OpenAI-style `response_format` receive native JSON enforcement. Models that can produce structured text but do not support `response_format` receive the same strict JSON prompt but without the unsupported parameter. The final parser and deterministic editorial gates remain authoritative.

This is required for Nemotron Ultra and Nano Omni, whose current OpenRouter documentation states that they support structured/tool use but do not support `response_format`.

## Failure policy

`401`, invalid credentials, and provider authentication failures disable the provider family for the current process.

Model permission/unavailability errors are model-scoped.

Groq `429`/quota errors are model-scoped. A Groq Qwen quota event must not disable Groq GPT-OSS.

OpenRouter daily/free-tier exhaustion is provider/family scoped because the free request allowance is a platform-level constraint.

Timeouts and 5xx errors are temporary model failures with one bounded retry.

## Discovery policy

`scripts/refresh_free_model_registry.py` runs before production. It validates the actual OpenRouter API key through `GET /api/v1/key`, refreshes the public OpenRouter model catalog, validates the Groq credential with its model catalog, updates runtime capability flags, and stores new free models only as `candidate_only` discovery entries.

The generated runtime registry lives under `artifacts/` and is never committed as production configuration. The canonical trust list remains in version-controlled YAML for auditability.

## Operational anti-burst controls

The router caps concurrent provider calls so a four-worker summarization stage does not create a burst against the same free endpoint. Provider calls have bounded timeouts and one retry for transient failures. This protects Groq free-plan token/request limits and reduces avoidable 429 cascades.

## Production health meaning

A green workflow means code/tests/policies completed successfully. It does not by itself mean that LLM quality was healthy. Runtime diagnostics therefore distinguish:

- provider credential validation;
- model availability;
- LLM call success/failover;
- editorial rejection;
- publication success.

A production run is considered operationally healthy only when at least one trusted core provider validates and the runtime log records successful LLM calls for the selected candidates. Zero publication may still be legitimate only when deterministic editorial/publication rejection evidence exists.
