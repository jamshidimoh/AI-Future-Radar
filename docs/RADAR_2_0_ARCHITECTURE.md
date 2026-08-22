# AI Future Radar 2.0 — Whole-System Architecture

**Status:** Architecture baseline — approved for implementation on a separate branch

**Branch:** `architecture/radar-2-0-foundation`

## 1. Purpose

AI Future Radar is a quality-first editorial intelligence system for discovering, consolidating, evaluating, explaining and publishing important developments in AI and adjacent future-facing technology.

The system is not intended to maximize the number of posts. Its primary objective is to maximize useful signal, factual integrity, source traceability and editorial quality while keeping the implementation understandable, resilient and inexpensive to operate.

The production policy remains:

- News evaluation window: 4 hours.
- Normal news: normally 0–1 high-quality story per evaluation window.
- Breaking news: may publish immediately when both quality and urgency thresholds are met.
- Education: 12-hour cadence, independently scheduled from news.
- Quality takes precedence over filling a quota.

These values are policy defaults and must remain configurable.

## 2. Design principles

1. **Story-centric:** the primary editorial unit is a story/event, not a URL or feed item.
2. **Evidence-first:** final content is generated from a bounded evidence record, not from a bare RSS snippet whenever stronger evidence is available.
3. **One editorial decision path:** no parallel Tier-0/leader/regular ranking engines with conflicting rules.
4. **Quality > quota:** a weak item is rejected rather than published to fill a slot.
5. **Fail closed at publication:** missing critical source, link, language, attribution or media requirements blocks publication.
6. **Risk-based verification:** verification depth scales with claim sensitivity, controversy and source strength.
7. **Diversity without complexity:** one ranking plus one lightweight diversity re-rank; no second ranking engine.
8. **Editorial memory:** recent publication history affects repetition/saturation, not just exact duplicate detection.
9. **Deterministic boundaries:** collectors collect; editorial logic selects; LLMs transform; delivery publishes; state records outcomes.
10. **Measurement before optimization:** cadence and score weights are calibrated from a Golden Dataset and production telemetry rather than guesswork.

## 3. Whole-system view

```text
Sources
  |
  v
DISCOVERY
  |
  v
STORY ENGINE
  |--- normalize
  |--- entity / person resolution
  |--- story clustering
  |--- canonical story + source set
  |
  v
SCORE + SELECT
  |--- relevance
  |--- importance
  |--- evidence quality
  |--- freshness
  |--- future / strategic value
  |--- saturation / repetition penalty
  |--- lightweight diversity re-rank
  |
  v
EVIDENCE BUILD
  |--- primary source
  |--- corroboration when risk requires it
  |--- official/original interview evidence when available
  |
  v
WRITE + VERIFY
  |--- LLM draft from Story + Evidence
  |--- language / factual / attribution checks
  |--- canonical message contract
  |--- image relevance/provenance check
  |
  v
PUBLISH
  |--- Telegram destination check
  |--- delivery
  |--- message_id capture
  |--- publication ledger
  |
  v
MEASURE
  |--- delivery and audience telemetry
  |--- editorial memory
  |--- future calibration
```

## 4. Current production architecture (as-is baseline)

The current repository is a Python batch pipeline with top-level orchestration in `main.py`, a production wrapper in `production_entrypoint.py`, and a resilient launcher in `production_resilient_runner.py`.

Current flow:

```text
RSS + YouTube + Google News
        |
        v
leader identity recovery
        |
        v
link/history dedup
        |
        v
protected leader split + regular pool
        |
        v
AI relevance gate on regular pool
        |
        v
editorial enrichment / mission / signal scoring
        |
        v
semantic clustering / canonical story selection
        |
        v
global ranking + constrained selection
        |
        v
LLM summary + editorial review
        |
        v
language / length / publication gates
        |
        v
image resolution + Telegram formatting
        |
        v
Telegram delivery + publication ledger
        |
        v
persisted seen/cadence/feedback state
```

This is the current behavior being refactored, not the target design.

### 4.1 Current orchestration responsibilities

`main.py` currently orchestrates discovery, leader recognition, link deduplication, protected/regular splitting, AI relevance filtering, semantic deduplication, enrichment, ranking and final publication preparation.

`production_entrypoint.py` currently adds cadence, Telegram feedback, educational cadence, selection feedback bonuses, publication policy, summary integration, Telegram delivery and state persistence.

`production_resilient_runner.py` wraps production execution with education-source resilience and a `faulthandler` timeout diagnostic.

This separation must be improved because editorial selection and production policy currently overlap in several places.

### 4.2 Current configuration domains

Configuration is distributed across YAML files including:

- `config/sources.yaml` — monitored sources and categories.
- `config/leader_watchlist.yaml` — priority people, leader queries and selected YouTube channels.
- `config/selection_policy.yaml` — post/window limits, similarity threshold and editorial policy.
- `config/mission_policy.yaml` — mission/priority dimensions.
- `config/editorial_priority_people.yaml` — priority-person detection data.
- `config/deep_concepts.yaml` and `config/deep_source_policy.yaml` — deep/education source policy.
- `config/education_curriculum.yaml` — educational sequence.
- `config/emerging_terminology.yaml` — terminology support.
- `config/pioneers.yaml` — configured people/source metadata.

The migration should reduce overlap between these files without forcing all configuration into one giant file.

### 4.3 Current state

Persistent production state includes:

- seen URLs/signatures and source history,
- Telegram feedback,
- publication/cadence state,
- educational progress.

Publication must be recorded only after a Telegram `message_id` confirms delivery.

## 5. Target Radar 2.0 components

### 5.1 Discovery

Collectors produce normalized `SourceItem` objects. A collector does not decide whether content deserves publication.

Required normalized fields include at least:

```text
source_id
source_name
source_type
url
published_at
raw_title
raw_summary
raw_description
content_type
image_url (optional)
entities (optional)
watch_person (optional)
```

Transport resilience remains inside collectors. YouTube may use the configured transport ladder; RSS/Google News failures remain isolated per source.

### 5.2 Story Engine

The Story Engine converts many source items into a canonical `Story`.

Conceptual schema:

```text
story_id
canonical_title
first_seen_at
last_seen_at
people[]
organizations[]
topics[]
content_types[]
sources[]
evidence[]
leader_relevance
interview_signal
research_signal
importance_features
```

Story construction includes:

1. URL/link normalization.
2. Entity/person resolution.
3. Semantic clustering.
4. Canonical-source selection.
5. Historical story saturation lookup.

Exact duplicate detection and story clustering belong here. They should not be repeatedly re-applied in later ranking pools.

### 5.3 Score + Select

The target uses one primary editorial score. Initial components are:

```text
Importance
Relevance
Evidence quality
Freshness
Future / strategic value
- Saturation / repetition penalty
```

Initial weights are configurable starting values, not permanent truths. A later calibration phase may tune them using the Golden Dataset and production observations.

Leader/watchlist information is a feature, not an independent publication pipeline. A substantive interview with a configured leader can score highly because of its content characteristics; a weak article mentioning a leader must not receive an automatic publication slot.

After primary ranking, a lightweight diversity re-rank prevents domination by one person, company, topic, source or content type.

### 5.4 Evidence Builder

Evidence depth is risk-based.

Low-risk official statement:

```text
primary official source may be sufficient
```

Important/contested/high-impact claim:

```text
primary/original evidence
+
independent corroboration when available
```

Interview/podcast:

```text
original video/audio/page
+
transcript or corroborating source when available
```

Evidence is stored as structured provenance metadata so that the generated text can be audited without exposing internal evidence details in every Telegram message.

### 5.5 Write + Verify

The LLM receives the canonical Story plus the bounded Evidence record.

The canonical output contract is:

```text
 title
 summary
 why_it_matters
 source_name
 source_url
 chatgpt_url
 content_type

 optional:
 speaker
 quote
 image
```

Verification must be deterministic where possible. At minimum:

- source URL exists and is canonical,
- required fields are present,
- required Persian fields satisfy the language gate,
- quotes are attributable when present,
- numeric/model/version claims remain supported by evidence,
- image is relevant to the story when present,
- Telegram formatting preserves all critical links.

If a critical check fails, the story is rejected rather than emitted through a lossy fallback.

### 5.6 Publish

Telegram is a delivery target, not an editorial engine.

The publication layer enforces one canonical message contract. The minimum user-facing structure is:

```text
[Title]

[Summary]

Why it matters?
[Importance / consequence]

[Source]

[Main source link]
[ChatGPT analysis link]
```

Quote, speaker and image are optional. Image is subordinate to content integrity: if using a photo would require removing a required text/link, the image is dropped and the complete text message is sent.

### 5.7 Measure + Editorial Memory

The system records production outcomes and available channel feedback. At minimum, internal telemetry should connect the published story to:

```text
story_id
publish_time
content_type
people/topics
source
score
selection_reason
message_id
publish_success
```

Where available, audience metrics can later inform calibration. Online learning is intentionally excluded from the first migration; measurement and bounded calibration come first.

## 6. Cadence and publication policy

### News

A 4-hour window is a decision window, not an obligation to publish.

Default policy:

```text
0–1 normal high-quality story per 4-hour window
~3–4 normal high-quality stories/day in ordinary conditions
```

A breaking story can override the window only when urgency and quality thresholds are both met.

### Education

Education remains independent from news and uses a 12-hour cadence. It must not consume news ranking capacity.

### Spacing

A conservative normal-news minimum gap may be used initially, but the exact value is not permanently encoded as a product truth. It should be tuned from actual channel telemetry after sufficient observations.

## 7. Golden Dataset and evaluation

Before replacing the current editorial engine, build a representative historical dataset of roughly 100–200 stories from prior Radar runs.

Each labeled record should capture, where possible:

- publish/reject decision,
- expected importance,
- best source,
- duplicate/story identity,
- leader/interview relevance,
- acceptable evidence level,
- expected rank band,
- expected content quality.

Current vs target evaluation must track at least:

```text
Relevance
Evidence coverage
Factuality / attribution
Leader-interview recall
Duplicate rate
Diversity
Freshness
Publication success
Latency
```

No major migration should be declared successful only because unit tests pass.

## 8. Reliability and performance

The system must remain bounded and observable.

Known production evidence already showed a severe pre-ranking bottleneck in feature preparation: a recent run recorded approximately 854.55 seconds for 29 items. This makes performance work part of the architecture migration, not an optional cleanup.

Hard requirements:

- per-stage timing,
- bounded collector calls,
- provider circuit breaking for repeated quota/auth failures,
- no repeated expensive feature extraction for the same story,
- no full LLM generation for discarded candidates,
- explicit timeout diagnostics.

The 18-minute workflow timeout remains an outer safety guard, not the solution to latency.

## 9. CI/CD and production boundary

GitHub Actions currently contains separate workflows for:

- quality/regression tests,
- Signal Engine CI,
- Story Rotation tests,
- production run,
- GitHub Pages documentation.

The target architecture should keep CI responsible for code/contract validation and keep Production responsible for live integration validation.

A migration PR must pass:

1. import/compile checks,
2. configuration validation,
3. full regression contract suite,
4. Story Engine tests,
5. Story selection tests,
6. Evidence/QA tests,
7. Telegram publication contract tests,
8. performance budget tests where deterministic.

Production validation remains separate and must inspect real run logs and publication artifacts.

## 10. Migration strategy

Migration is incremental and reversible.

### Phase A — Freeze and baseline

- Keep current production path unchanged.
- Add architecture specification and Golden Dataset format.
- Capture baseline metrics from the current engine.

### Phase B — Introduce Story model

- Add `SourceItem` and `Story` structures.
- Build Story clustering behind a new boundary.
- Keep old selection engine as the fallback path.

### Phase C — Replace ranking

- Introduce one story score.
- Add lightweight diversity re-rank.
- Use leader/watchlist only as features.
- Keep old ranking available behind a feature flag until the benchmark passes.

### Phase D — Evidence + generation

- Add bounded evidence records.
- Move generation to Story + Evidence.
- Enforce canonical publication contract and deterministic QA.

### Phase E — Cutover

- Run old and new engines against the Golden Dataset.
- Compare quality and latency.
- Enable the new engine in Production only after acceptance thresholds pass.

### Phase F — Cleanup

Only after stable production validation:

- remove obsolete ranking/pool paths,
- remove redundant dedup passes,
- remove obsolete leader-protection branches,
- update documentation and regression tests.

## 11. Explicit non-goals

The first Radar 2.0 migration will not introduce:

- autonomous agent loops,
- online reinforcement learning,
- a permanent model server,
- a complex knowledge graph platform,
- mandatory multi-source retrieval for every story,
- automatic publication based on raw LLM confidence,
- mandatory C2PA metadata for every image.

These exclusions are deliberate to protect simplicity and reliability.

## 12. Acceptance criteria for the new architecture

The migration is considered complete only when all of the following are true:

- Story-level deduplication is the canonical duplicate mechanism.
- One editorial score and one diversity re-rank replace conflicting parallel ranking paths.
- Leader watchlist remains effective without creating a separate publication pipeline.
- High-impact content receives stronger evidence verification than low-risk content.
- No publication can lose required source/ChatGPT links or key text because of image/caption constraints.
- A quality failure rejects a story instead of generating a lossy fallback message.
- News and education cadence remain independent.
- Production latency is within a measurable budget below the outer workflow timeout.
- Golden Dataset metrics show an improvement over the current baseline without materially increasing operational complexity.
