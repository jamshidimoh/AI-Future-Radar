# AI Future Radar — Production Final Acceptance Gate

This document is the release boundary for declaring the repository production-complete. It separates deterministic repository guarantees from evidence that can only be obtained from real production runs. Once the deterministic gates below are green, they are frozen; later improvements are optimization work unless they violate an invariant.

## Deterministic gates — frozen invariants

- [x] One canonical production orchestration path remains in `production_entrypoint.py`.
- [x] Ranked selection is provided by `period_ranked_pipeline._global_ranked_selection`.
- [x] Selected normal stories receive `period_rank` and contiguous `normal_period_rank` values.
- [x] The normal-news adaptive baseline applies uniformly across the rank window, including `normal_rank=1`; rank 1 is never a score-policy bypass.
- [x] Protected leader/interview stories are exempt only through the explicit Tier-0/protected routing contract and still pass Story Identity and publication-quality checks.
- [x] Canonical URL/title/semantic publication guards prevent duplicate publication; cross-language duplicates remain blocked.
- [x] Telegram delivery is represented through the typed delivery contract and publication ledger; publication state advances only from confirmed delivery.
- [x] Education is an independent scheduled stream; education failure must not rerun or duplicate the completed news orchestration.
- [x] Editorial language/quality gates remain authoritative for published news.
- [x] Mission coverage is preserved by the configured editorial portfolio: AI core, AI–emerging-technology convergence, mind/cognition/consciousness, and future/governance. fileciteturn39file0
- [x] Source quality and rotation remain bounded by the configured evidence hierarchy and diversity policy; community sources are not a normal-news substitute. fileciteturn39file0
- [x] Repository regression tests cover canonical deduplication, Story Identity, delivery outcomes, editorial quality, protected leaders, ranking/diversity, and the final ranking/publication boundary.
- [x] A real publication baseline is present in `data/publication_state.json`. fileciteturn40file0

## Real-production evidence required before final release declaration

The following evidence cannot be honestly proven by static CI alone and must be observed from real production runs:

1. Three consecutive production runs on the same accepted code lineage complete without timeout or manual intervention.
2. The runs demonstrate both outcomes: at least one valid story is published when an eligible candidate exists, and a run with no candidate above the adaptive publication baseline safely publishes nothing rather than lowering the quality floor.
3. No duplicate Telegram publication is produced across the observation window.
4. A story with an image preserves the canonical full-text publication contract; image failure cannot truncate or replace the text publication.
5. No eligible normal candidate reaches publication with `normal_rank=None`, and no `normal_rank=1` candidate bypasses the adaptive score policy.
6. Leader/interview candidates from the configured watchlist remain discoverable and publishable when they meet quality thresholds.
7. A provider 429/5xx/timeout/empty-response does not abort unrelated publication paths.
8. Persisted publication state advances only from confirmed delivery and remains internally consistent after the run.
9. The observation window contains no regression in the mission portfolio: the system may publish fewer stories or zero stories when quality constraints require it, but it must not silently collapse into a generic low-signal feed.

## What does NOT constitute a failure

- A production run publishes zero news items because no candidate satisfies the configured relevance, evidence, diversity, language, or adaptive publication policy.
- A candidate is rejected because its score is below the current adaptive baseline.
- An education run is skipped or independently recovered because its source/language contract is unavailable, provided the news pipeline remains single-pass and consistent.
- A better source, model, signal, or ranking formula is discovered later. Such findings are optimization opportunities, not regressions, unless a frozen invariant is violated.

## Change discipline after acceptance

Do not modify frozen ranking/publication invariants merely to increase publication volume. Any change that affects ranking, relevance, publication policy, deduplication, delivery, resilience, or mission coverage must first add or update a deterministic regression test and then pass the full acceptance workflow before production validation.

## Release decision

A release may be labelled `Production Final` only when all deterministic gates are green and every real-production evidence item above has been observed and recorded against a specific commit SHA.

The repository must not be considered permanently "bug-free". The acceptance boundary instead defines when the system is production-safe, mission-aligned, and stable enough that subsequent work is measured as controlled optimization rather than open-ended repair.