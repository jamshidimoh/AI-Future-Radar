# Production publication contract

1. Every eligible news candidate enters one global editorial ranking after deduplication and quality gating.
2. `period_rank` is the global rank for the period; it is assigned before summarization/publication.
3. Tier-0 substantive interviews, podcasts, Q&A/keynotes and attributable quotes from the configured top AI voices are retained outside the normal-news quota.
4. Tier-0 content may publish regardless of global `period_rank`, subject to freshness, deduplication, attribution, language and editorial-quality gates.
5. `normal_period_rank` is assigned independently to non-Tier-0 news so a high number of Tier-0 items cannot suppress normal-news coverage.
6. Normal-news rank 1 is the primary candidate. Normal-score eligibility uses the current adaptive normal-news floor; the last published normal score is diagnostic, not a hard publication threshold.
7. At most two normal-news extras may be published; `normal_news_count <= 3` per period. Tier-0 publications do not consume this quota.
8. Mind/Ideas/Voices is independent from the normal-news score floor, but its own independent quality score must be at least `50.0`; low-quality special-lane candidates are rejected rather than published merely to satisfy coverage.
9. Major AI model releases/updates from the configured major labs receive the highest priority within the normal-news stream and must pass substantive model-release detection.
10. Duplicate and blocked candidates cannot publish. A skipped or failed candidate must not advance the normal-news baseline.
11. Every successful Telegram news delivery updates the publication ledger. The ledger records the score of the last published news item, while `last_published_normal_news_score` is the baseline used by the normal-news comparative policy.
12. Education remains on its independent 12-hour cadence and does not consume the news quota.
13. Telegram photo captions are a compact rendering only; the canonical full Persian message remains the source of truth. Photo caption generation must always stay within the Telegram-safe limit and must never shorten the canonical message.
