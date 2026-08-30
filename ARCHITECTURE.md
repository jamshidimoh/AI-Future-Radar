# AI Future Radar — Production Architecture

## Purpose

AI Future Radar is a deterministic editorial pipeline that discovers technology signals, removes duplicates, evaluates relevance and evidence, constructs a mission-aware editorial portfolio, uses an LLM only for transformation and bounded quality repair, and delivers validated content to Telegram.

The current production cadence is one normal news publication every 4 hours and one educational publication every 12 hours. Normal news capacity is three items per run; Tier-0 protected material is quota-exempt. Education is due every three production runs, based on persisted state rather than wall-clock assumptions.

The system must remain useful when any individual LLM provider, RSS feed, YouTube transport, or image source is unavailable.

## Runtime contract

```text
Discovery
  -> URL/link normalization and deduplication
  -> AI relevance gate
  -> semantic story clustering / canonical story
  -> editorial enrichment and scoring
  -> Trend Intelligence sidecar
       -> signal qualification
       -> evidence annotation
       -> trend clustering
       -> temporal tracking
       -> trend state / driver mapping
       -> cross-domain convergence
  -> Unified Editorial Contract
       -> protected-stream eligibility
       -> mission coverage opportunities
       -> authoritative/community boundary
       -> adaptive source diversity
       -> content-type and mission-area caps
       -> replacement-aware candidate window (6)
  -> LLM transformation
  -> language / schema / editorial-quality gates
  -> ranked replacement candidates when a selected item fails QA
  -> source-image validation
  -> Publication Contract
  -> Telegram delivery
  -> persistent seen/history/cadence state
```

Trend Intelligence is a decoupled evolution layer. It may observe and persist trend state without increasing publication capacity or bypassing any publication gate. Its reference design is `docs/TREND_INTELLIGENCE_ARCHITECTURE.md`; its initial policy is `config/trend_intelligence.yaml`; deterministic primitives live in `src/trend_intelligence.py`.

Cross-cutting production invariants are declared in `config/production_contract.yaml`. Mission taxonomy and targets remain in `config/mission_policy.yaml`. Execution mechanics remain in `config/selection_policy.yaml`. `src/unified_editorial_selection.py` is the executable bridge: it resolves those layers into one deterministic portfolio contract.

Collectors are not responsible for editorial selection. LLMs are not the sole authority for monitored-domain eligibility or Trend identity. The deterministic relevance, provenance, mission, diversity, quality, evidence and publication contracts remain authoritative; LLMs transform source material and may perform one bounded editorial repair.

## Trend Intelligence

The Radar maintains two separate objects: a `canonical story` for publication deduplication and a `trend cluster` for longitudinal intelligence. One cluster may contain many stories, sources and content types; one story may contribute to only the clusters supported by its evidence.

Trend Intelligence keeps `source_tier`, `evidence_level`, `signal_score`, `trend_score` and `forecast_confidence` independent. A high-tier interview is a valuable discovery signal but is not automatically strong scientific evidence. Primary research can outrank expert commentary on evidence strength without receiving a higher discovery tier.

The trend layer explicitly covers AI, emerging technologies, robotics, quantum, biotechnology, brain-computer interfaces, consciousness/cognition, philosophy of science and futures/foresight. The existing AI-first publication policy remains authoritative for normal news publication; tracking a non-AI cluster does not create a publication bypass.

Weak signals are retained even when they are too early or too uncertain to publish. Repeated stories from the same source do not create independent evidence. Supporting evidence and counter-evidence are stored separately. Cluster state is longitudinal: `weak_signal`, `emerging`, `accelerating`, `established`, `fading`, or `disconfirmed`.

The preferred future evolution is:

```text
Weak Signals
   -> Emerging Trend Clusters
   -> Drivers / Cross-domain Convergence
   -> Three Horizons / Impact-Uncertainty
   -> Scenarios / Opportunities / Risks
   -> Strategic Technology Intelligence
```

Forecasts remain explicitly uncertain and cannot overwrite the evidence state.

## Unified editorial selection

The selector has four explicit objectives, in order:

1. Protect eligible Tier-0/leader material without creating a publication bypass.
2. Give eligible mission areas and research evidence explicit coverage opportunities.
3. Prefer distinct sources in the current run while treating historical source usage as a bounded preference signal rather than a hard exclusion.
4. Fill remaining capacity by calibrated editorial score while respecting hard source, content-type, mission-area and community limits.

Normal publication capacity is `max_posts=3`. The selector constructs a six-item candidate window (`candidate_window=6`); candidates beyond the first three are replacement candidates and never increase the publication quota. Transformation, editorial QA, language and publication policy apply equally to primary and replacement candidates.

`max_items_per_source=2` is the hard ceiling, while `mission.max_same_source=1` is the preferred same-source target. This distinction prevents source concentration without collapsing the run when only a small set of sources are available.

Mission targets are opportunities, not fabricated quotas. When an eligible candidate for convergence, mind/cognition, future/governance or research exists, the selector gives it an explicit opportunity; when no eligible candidate exists, the system continues without inventing coverage.

## Discovery source boundary

The source registry is authoritative for discovery. A globally excluded source is not a Radar source and must not be searched, crawled, ingested, ranked, selected, or published. Exclusions are enforced before network discovery where the query/source is known and again at ingestion as a defense against accidental upstream results.

The current global exclusion is `arxiv.org` (including `export.arxiv.org`). It is intentionally absent from the source registry. Research coverage must come from validated non-ArXiv sources such as peer-reviewed publishers, universities, research laboratories, scientific organizations, standards bodies, credible industry reports, and substantive expert content.

This is a source boundary, not a ranking penalty or editorial exception. No downstream component should contain source-specific arXiv scoring, quota, concentration, or fallback logic.

## Discovery resilience

### YouTube

YouTube discovery uses a transport ladder:

1. YouTube Data API v3 when `YOUTUBE_API_KEY` is configured.
2. Official channel RSS.
3. Official channel page with structured `ytInitialData` extraction.
4. Regex HTML fallback.

Monitored channels should prefer stable `handle` identifiers over manually copied channel IDs when possible. This avoids silently breaking monitoring when a stale ID is present in configuration. A failure of RSS must not be treated as a channel failure until page fallback has also been attempted.

Dedicated high-value channels such as MIT CSAIL — Building 32 are represented as protected sources rather than being forced into a person-based leader model.

### General RSS

RSS failures are isolated per source. One inaccessible university or specialist feed must not fail the run. Equivalent Google News or specialist-source queries remain available when configured.

## Editorial protection

The radar has two distinct protected classes:

- People: high-priority leaders such as Andrew Ng, Sam Altman, Demis Hassabis, Elon Musk, Jensen Huang and other configured leaders.
- Protected sources: authoritative recurring sources such as MIT CSAIL — Building 32.

Protected leader slots enforce diversity. The same person cannot occupy multiple protected slots in one run. Protected sources are priority candidates, not AI-relevance or publication-quality bypasses. They still cross normal deduplication, language, editorial-quality and delivery gates.

Protected classification and publication classification must remain aligned: a candidate marked Tier-0 by ranking must carry the same semantic status into the Publication Contract. A leader activity item is not automatically an interview; the interview/activity reason must remain explicit.

## Provider architecture

The LLM router is provider-agnostic. A provider that reports quota exhaustion, payment exhaustion, or authentication failure is disabled for the remainder of the current run. This prevents repeated failed calls for every selected story.

If all providers fail, the item is not published. Invalid LLM JSON and insufficient Persian-language output never reach Telegram.

A failed transformation or editorial-quality check does not automatically fail the whole run. The candidate is blocked and a lower-ranked replacement candidate may be attempted when one exists, subject to the same publication contract. This is bounded replacement, not quality relaxation.

## Telegram delivery contract

Publication is fail-closed:

- Empty text is never sent.
- Telegram destination and bot permissions are verified before publication.
- A source image must resolve to an actual raster image before it can be sent.
- For posts within Telegram's photo-caption limit, the preferred delivery is one photo message containing the complete post.
- For longer posts, the complete text is sent first and the validated image is sent afterward with a meaningful caption and source link.
- An invalid or unavailable image produces text-only publication rather than an empty/blank image message.
- The returned Telegram `message_id` is captured before the item is marked as published/seen.

This distinction is intentional: a long Telegram post cannot always be represented as one photo-caption message without truncation. The contract therefore prioritizes content integrity over forcing an oversized caption into a single message.

## Persian / RTL contract

News and education renderers use directional isolation around visual rows and isolate Latin runs such as model names, companies and English terminology. Educational rendering additionally validates every non-empty logical row before publication. This is a publication contract, not merely a cosmetic formatting preference.

## State and concurrency

Runtime state includes seen URLs/signatures, Telegram feedback, educational progress and publication cadence. State is currently persisted in Git after a production run. The workflow rebases the state commit against the latest `main` before pushing and retries the push.

This Git-backed state is an explicit current-stage trade-off. The code/state separation should be revisited before treating the Radar as a high-concurrency multi-worker service.

Trend state should eventually be persisted separately from publication state. It requires append-friendly signal history, stable cluster IDs, merge/split lineage and reproducible recomputation. Until that storage layer is introduced, the deterministic engine remains an evolution-sidecar and does not claim full longitudinal persistence.

## Observability

Every production run reports:

- cadence decision
- discovery counts by transport
- YouTube fallback source used per channel
- leader/protected-source discovery and diversity decisions
- link and semantic deduplication
- AI relevance gate
- unified mission/source selection decisions and candidate-window size
- Trend Intelligence signal count, cluster count, state distribution and top cluster audit summaries when enabled
- provider success/fallback behavior
- language/editorial-quality/replacement decisions
- Telegram message IDs and delivery mode
- state persistence outcome

Ranking and trend audit artifacts should permit reconstruction of why each published or blocked candidate crossed each major boundary and why a signal joined or did not join a cluster.

## Regression strategy

The regression suite protects production contracts rather than only unit-level helpers. It covers cadence, editorial selection, leader priority, MIT/Building 32 priority, canonical deduplication, YouTube resolution/fallback, image validation/delivery, Telegram formatting, educational RTL, language gates, source exclusion, source diversity, mission coverage and configuration invariants.

Trend Intelligence additionally requires deterministic clustering tests, source-independence tests, cross-domain convergence tests and explicit separation of source tier from evidence strength.

`tests/test_production_contract.py` checks that the protected-source declaration, mission targets, selection mechanics, source registry, quality thresholds, source boundary and architecture document remain synchronized. `tests/test_unified_editorial_selection.py` tests behavior, including distinct-source preference, adaptive backfill, mission coverage opportunities, community exclusion and hard caps.

A contract drift is a CI failure, not a silent editorial change. Any change to a production contract must update the corresponding regression test before production is considered ready.

## Design boundary

The pipeline remains batch-oriented. It does not require an agent loop, autonomous tool planning, or a permanent model server. Future extensions should be added behind discovery, editorial selection, Trend Intelligence, transformation, delivery and state boundaries rather than inserting provider-specific logic throughout `main.py`.
