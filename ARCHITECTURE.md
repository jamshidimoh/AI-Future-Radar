# AI Future Radar — Production Architecture

## Purpose

AI Future Radar is a deterministic editorial pipeline that discovers technology signals, removes duplicates, scores stories, selects a small editorial set, uses an LLM only for transformation, and delivers validated content to Telegram.

The current production cadence is one news publication every 4 hours and one educational publication every 12 hours. Education is due every three production runs, based on persisted state rather than wall-clock assumptions.

The system must remain useful when any individual LLM provider, RSS feed, YouTube transport, or image source is unavailable.

## Runtime contract

```text
Discovery
  -> URL/link normalization and deduplication
  -> AI relevance gate
  -> semantic story clustering / canonical story
  -> editorial enrichment and scoring
  -> constrained selection
  -> LLM transformation (draft + editorial pass)
  -> language / schema / publication gates
  -> source-image validation
  -> Telegram delivery
  -> persistent seen/history/cadence state
```

Collectors are not responsible for editorial selection. LLMs are not responsible for deciding whether an item belongs to the monitored domain. The editorial module is the scoring authority; production orchestration adds only explicit runtime contracts such as cadence, protected-source handling, language gates, and delivery safety.

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

Protected slots enforce diversity. The same person cannot occupy multiple protected slots in one run. Protected sources are likewise not duplicated by source. Fresh protected items are considered before ordinary editorial ranking, while regular content still passes the normal AI relevance and deduplication gates.

Andrew Ng is currently a Featured Tier-1 leader with priority 11. MIT CSAIL — Building 32 is a protected source with the same high priority.

## Provider architecture

The LLM router is provider-agnostic. A provider that reports quota exhaustion, payment exhaustion, or authentication failure is disabled for the remainder of the current run. This prevents repeated failed calls for every selected story.

If all providers fail, the item is not published. Invalid LLM JSON and insufficient Persian-language output never reach Telegram.

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

Runtime state includes seen URLs/signatures, Telegram feedback, educational progress and publication cadence. State is committed back to `main` only after a successful production run.

Because production state is persisted in Git, the workflow rebases the state commit against the latest `main` before pushing and retries the push. This prevents a successful bot run from being reported as failed solely because another commit reached `main` during execution.

## Observability

Every production run reports:

- cadence decision
- discovery counts by transport
- YouTube fallback source used per channel
- leader/protected-source discovery and diversity decisions
- link and semantic deduplication
- AI relevance gate
- provider success/fallback behavior
- language/publication gates
- Telegram message IDs and delivery mode
- state persistence outcome

## Regression strategy

The regression suite protects the production contracts rather than only unit-level helpers. It covers cadence, editorial selection, leader priority, MIT/Building 32 priority, canonical deduplication, YouTube resolution/fallback, image validation/delivery, Telegram formatting, educational RTL, language gates and configuration invariants.

Any change to one of these contracts must update the corresponding regression test before production is considered ready.

## Design boundary

The pipeline remains batch-oriented. It does not require an agent loop, autonomous tool planning, or a permanent model server. Future extensions should be added behind discovery, editorial, transformation, delivery and state boundaries rather than inserting provider-specific logic throughout `main.py`.
