# P1 Editorial/Signal Correlation Audit — Baseline

Date: 2026-09-01
Branch: `audit/p1-editorial-signal-golden`
Behavior changes: none

## Baseline

P0 Ruff repository audit baseline: **21 diagnostics**. This count is recorded in PR #78 and is the comparison point for P1.

## Current data flow

1. `editorial_clean.enrich_items()` computes editorial features and the pre-signal `editorial_score`.
2. `signal_engine.enrich_signal_items()` computes a separate signal vector and `signal_score`.
3. `main._apply_signal_ranking()` creates an intermediate `editorial_score = editorial_score_pre_signal + 0.30 * signal_score`.
4. `main.py` uses that intermediate score for pre-selection ordering before `gate_story_candidates()`.
5. `period_ranked_pipeline._base_editorial_score()` deliberately prefers `editorial_score_pre_signal` over the inflated `editorial_score`.
6. `period_ranked_pipeline.canonical_rank_score()` therefore uses `0.75 * editorial_score_pre_signal + 0.25 * signal_score` for final period ranking.

## Finding: final-score compounding is prevented

The hypothesis that the `0.30` signal injection is compounded again by the `0.75/0.25` final formula is **false**.

`_base_editorial_score()` checks `editorial_score_pre_signal` before `editorial_score`, so the inflated intermediate value is not used by `canonical_rank_score()`.

## Finding: upstream cluster ordering uses the inflated score

This is **confirmed directly from the code**. `main._apply_signal_ranking()` inflates `editorial_score`; `main.py` sorts by it before `gate_story_candidates()`; `src/story_gate.py` ranks by `editorial_score` and then `signal_score`; `src/story_identity.py` applies first-wins duplicate elimination.

Thus the causal path is:

`inflated editorial_score` → `story_gate.rank()` → `deduplicate_stories()` first-wins traversal → surviving story representative.

The mechanism is confirmed. Its frequency and magnitude in realistic duplicate/near-duplicate clusters remain empirical.

Additionally, `signal_score` is a second upstream tie-breaker immediately after the already signal-inflated `editorial_score`, so the same signal can influence ordering twice at this stage.

## Direct feature overlap

| Concept | Editorial layer | Signal layer | Correlation risk |
|---|---|---|---|
| Freshness | freshness contribution | `freshness_score()` | High |
| Novelty | `novelty_score` | `novelty_score()` | High |
| Future impact | `future_relevance` | `future_impact_score()` | High |
| Evidence / credibility | `scientific_credibility` | `evidence_strength`, `source_quality` | Medium–High |
| Technical depth | editorial readiness/classification | `technical_significance_score()` | Medium |
| Strategic relevance | strategic forecast / mission metadata | `strategic_relevance_score()` | Medium–High |
| Expert/leader influence | leader priority | `expert_influence_score()` | High for leader items |
| Trend | convergence/topic classification | `trend_alignment_score()` | Medium |
| Source quality | source tier in credibility | `source_quality_score()` | High |

## Protected-stream attribution

Leader/interview state is represented in policy/editorial metadata and can independently influence signal expert-influence scoring. Attribution rules should be explicit before any scoring redesign.

## Golden dataset

`tests/fixtures/p1_golden_dataset.json` freezes 12 deterministic scenarios covering core AI research, expert interview, quantum+AI, consciousness/cognition+AI, BCI+AI, embodied robotics, bio/AI, infrastructure/deployment, future/risk/governance, low-evidence community content, quantum out-of-scope content, and a major multimodal model release.

Expected labels are qualitative and do not prescribe a new score.

## Measurement harness

`tests/test_p1_story_gate_attribution.py` is audit-only. It runs the 12 fixtures through the real editorial and signal enrichers, reproduces the production story-gate key and a counterfactual pre-signal key, then performs a bounded sensitivity experiment using identical story identity with controlled scoring perturbations.

The sensitivity result is not a live-traffic frequency estimate. The appropriate next step is to compare it with a retained sample of actual duplicate/near-duplicate clusters.

## Next measurements

1. Pairwise feature correlation after both enrichers.
2. Marginal contribution of overlapping semantic concepts.
3. Leader-specific attribution between editorial priority and signal expert influence.
4. Story-gate representative sensitivity to the inflated intermediate score.
5. Representative changes on real duplicate/near-duplicate clusters.
6. Ruff count on the same repository surface, using 21 as baseline.

No production scoring, policy, or selection behavior is changed on this branch.
