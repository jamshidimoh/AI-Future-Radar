# AI Future Radar — Production Final Acceptance Gate

This document is the release gate for declaring the repository production-complete. It separates deterministic repository guarantees from evidence that can only be obtained from real scheduled runs.

## Deterministic gates

- [x] One canonical production orchestration path remains in `production_entrypoint.py`.
- [x] Ranked selection is provided by `period_ranked_pipeline._global_ranked_selection`.
- [x] Selected normal stories receive `period_rank` and contiguous `normal_period_rank` values.
- [x] Protected leader/interview stories remain exempt from the normal-news quota while preserving Story Identity checks.
- [x] Telegram delivery is represented through the typed delivery contract and publication ledger.
- [x] Repository regression tests cover canonical deduplication, Story Identity, delivery outcomes, editorial quality, protected leaders, and the final ranking/publication boundary.
- [x] A real production publication baseline is present in `data/publication_state.json` (run 116, last published score 84.94 on 2026-08-22).

## Real-production evidence required before final release declaration

The following items cannot honestly be proven by static CI alone and must be observed from the scheduled production workflow:

1. Three consecutive scheduled runs complete without timeout or manual intervention.
2. At least one valid story is published during the observation window.
3. No duplicate Telegram publication is produced across the observation window.
4. A story with an image preserves the canonical full-text publication contract; image failure cannot truncate or replace the text publication.
5. No eligible normal candidate reaches publication policy with `normal_rank=None`.
6. Leader/interview candidates from the configured watchlist remain discoverable and publishable when they meet quality thresholds.
7. A provider 429/5xx/timeout/empty-response does not abort unrelated publication paths.
8. The persisted publication state advances only from confirmed delivery.

## Release decision

A release may be labelled `Production Final` only when all deterministic gates are green and every real-production evidence item above has been observed and recorded against a specific commit SHA.

The repository must not mark this gate complete merely because a single run succeeds. The distinction is intentional: CI proves code contracts; repeated scheduled runs prove operational stability.
