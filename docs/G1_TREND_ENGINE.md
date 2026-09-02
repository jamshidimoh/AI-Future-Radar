# G1 — Deterministic Signal and Trend Engine

Status: VALIDATED — GREEN

G1 is publication-decoupled and remains isolated from `main` until controlled integration is accepted.

## Scope

The engine consumes normalized story/signal records and detects reproducible current-window clusters. It does not publish, alter editorial eligibility, modify source authority, or create persistent lineage.

## Input contract

Items may provide `id` or `story_id`, `title`, optional `summary`/`description`/`category`, an intrinsic `signal_score` or `signal_vector`, source identity, and optional novelty.

When a signal vector is supplied, intrinsic signal uses only novelty, future impact, technical significance, strategic relevance and trend alignment. Source Tier, source quality and evidence strength are not used to derive intrinsic signal.

## Deterministic clustering

Similarity is Jaccard similarity over normalized text tokens. The threshold is configurable and defaults to `0.45`.

Clustering uses complete-link behavior: every cross-pair between two candidate clusters must meet the threshold before they are merged. This prevents transitive A–B–C chains from becoming one trend when A and C are not directly similar enough.

Only clusters meeting `minimum_cluster_size` (default `2`) are emitted. Weak signals remain candidate trends; G1 does not impose an editorial publication floor.

## G1 output contract

Each emitted cluster contains a deterministic member-set hash `cluster_id`, sorted `member_ids`, `cluster_size`, deterministic `representative_id`, `mean_signal_score`, `mean_novelty_score`, `coherence`, `source_independence`, `trend_score`, `trend_confidence`, and `trend_class`.

Source Tier is not a trend-score dimension. Evidence authority and strength remain separate semantics for later gates.

## Configuration

`config/trend_engine.yaml` contains the G1 similarity threshold, minimum cluster size, confidence threshold, score weights and stopwords. Score weights must be non-negative and sum to `1.0`.

## Non-goals

G1 does not implement persistent registry/lineage, evidence graphs, temporal state, cross-domain convergence, or foresight. These belong to later gates.

## Acceptance evidence

Final immutable-HEAD validation completed successfully on `a4e2d07b8f156eacd516805ede27103fab5e9203`:

- Production Quality Gate: 474/474 tests passed.
- Final Production Acceptance: 474/474 regression tests passed.
- Final production acceptance suite: 6/6 passed.
- Frozen production acceptance contract: 6/6 passed.
- Production state contract: PASS (`run_number=269`, `last_published_news_score=64.0`, `last_published_normal_news_score=64.0`).

These runs checked out the exact G1 HEAD. The tested implementation therefore has revision-specific CI/acceptance evidence. Repeated execution determinism is also covered by the G1 test suite.

Production publication behavior remains unchanged pending G8 controlled integration.

G1 is validated. This does not imply overall project completion; G2 through G9 remain outstanding.
