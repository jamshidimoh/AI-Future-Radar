# AI Future Radar — Free Model Intelligence v2

## Decision

Do not treat LiteLLM, OpenRouter, Hugging Face, or any other gateway as the intelligence layer. The Radar needs a small policy engine whose only job is to answer: **which zero-price deployment is the best currently usable model for this task?**

The architecture is therefore:

`Radar task -> Free Model Intelligence -> qualified candidates -> deterministic rank -> execution gateway -> model`

The execution gateway is replaceable. LiteLLM is the default adapter because it provides a unified provider interface and deployment-level failure handling. OpenRouter is treated as a dynamic free-model catalog/execution source, not as the ranking authority. Hugging Face is a secondary discovery/execution source when its free credit is genuinely available. Direct provider adapters are permitted when they expose a stable free quota and a valid credential.

## Council roles

1. **Principal architect** — minimizes coupling and defines failure boundaries.
2. **LLM routing specialist** — separates model choice from transport/failover.
3. **ML evaluation specialist** — defines quality evidence and uncertainty.
4. **Platform/SRE engineer** — treats quota, authentication, latency, cooldown and health as first-class state.
5. **Security engineer** — prevents paid fallback, secret leakage and accidental billing.
6. **Python/test engineer** — enforces deterministic behavior and failure-mode tests.
7. **Editorial/domain specialist** — optimizes for Radar's actual work rather than generic benchmark prestige.

## Non-negotiable rules

- A model is eligible only if the current route is explicitly zero-price for the credential being used.
- Unknown pricing is **not** considered free.
- An expired, unauthorized, quota-exhausted, or failed deployment is unavailable for the current decision.
- Quality is primary. Priority is only a deterministic tie-breaker.
- A provider cannot promote a model merely by claiming it is high quality.
- Generic leaderboards are evidence, not truth for Radar tasks.
- Runtime evidence can demote a model without changing its long-term prior.
- The system must fail closed rather than silently use a paid endpoint.
- No single gateway is allowed to become the source of truth for quality.

## Candidate lifecycle

### 1. Discovery

Fetch current model catalogs from trusted provider APIs/catalogues. Normalize every candidate into a common record:

- provider family
- provider model id
- pricing status
- context window
- structured-output capability
- tool capability when relevant
- current credential status
- catalogue timestamp

OpenRouter's current free catalogue is a particularly useful discovery source because it exposes a continuously changing set of free variants. Its `openrouter/free` router is deliberately **not** used as the final selector because it selects among eligible free models rather than guaranteeing the highest-quality model.

### 2. Qualification

Apply hard gates before ranking:

`free == true && chat == true && required_output_capability == true && credential_valid == true && not_cooling_down`

Unknown values fail the gate.

### 3. Quality evidence

Quality is composed from four evidence classes:

- **External benchmark evidence:** current independent benchmark/leaderboard data where available.
- **Task-fit evidence:** Radar-specific evaluation dimensions such as instruction following, structured JSON reliability, concise summarization, editorial classification and long-context handling.
- **Runtime reliability:** success rate, quota failures, authentication failures and latency.
- **Freshness/confidence:** stale or weak evidence is discounted.

A benchmark score is never allowed to override a hard runtime failure.

### 4. Ranking

The default decision function is:

`utility = 0.55 * quality + 0.25 * task_fit + 0.15 * reliability + 0.05 * freshness`

Only after hard eligibility is established. The weights are configuration, not code constants.

When two candidates are statistically indistinguishable, prefer the one with better reliability, then lower latency, then explicit policy priority, then stable model id.

### 5. Execution

The selected candidate is sent through an execution adapter. The adapter may use LiteLLM, OpenRouter, Hugging Face, or a direct provider. Execution failure causes the intelligence layer to move to the next already-qualified candidate; it must not silently broaden the definition of free.

### 6. Learning

Each execution records only operational metadata needed for routing:

- selected deployment
- success/failure class
- latency
- output validation result
- timestamp

Persistent state is bounded and privacy-safe. It is used to adjust reliability, not to erase independent quality evidence.

## Why this design

OpenRouter's current free router is useful but explicitly random among currently eligible free models. That makes it a good availability mechanism but an insufficient quality selector. LiteLLM is strong as a unified execution and fallback layer, but it does not know which free model is best for Radar. Hugging Face similarly offers automatic provider selection, but its default policy optimizes provider selection for a specified model rather than choosing the best model globally.

The Radar therefore owns the intelligence decision and delegates transport to mature gateways.

## Validation plan

Before production activation, the implementation must pass:

1. deterministic ranking unit tests;
2. free-price hard-gate tests;
3. credential/auth/quota failure tests;
4. stale-catalog tests;
5. no-paid-fallback tests;
6. model-output validation tests;
7. real production smoke with at least one currently valid free deployment;
8. repeated production runs demonstrating stable selection and bounded latency.

The service is considered production-ready only when the real run proves that the selected model is the highest-ranked **eligible** candidate at decision time, not merely the first configured model that happens to answer.
