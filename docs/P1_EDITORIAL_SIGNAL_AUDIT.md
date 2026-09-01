# P1 Editorial/Signal Correlation Audit — Baseline

Date: 2026-09-01
Branch: `audit/p1-editorial-signal-golden`
Behavior changes: none

## Baseline

P0 Ruff repository audit baseline: **21 diagnostics**. This count is recorded in PR #78 and is the comparison point for P1.

## Current data flow

The production path is:

1. `editorial_clean.enrich_items()` computes editorial features and the pre-signal `editorial_score`.
2. `signal_engine.enrich_signal_items()` computes a separate signal vector and `signal_score`.
3. `main._apply_signal_ranking()` creates an intermediate `editorial_score = editorial_score_pre_signal + 0.30 * signal_score`.
4. `main.py` uses that intermediate score for the pre-selection ordering immediately before `gate_story_candidates()`.
5. `period_ranked_pipeline._base_editorial_score()` deliberately prefers `editorial_score_pre_signal` over the inflated `editorial_score`.
6. `period_ranked_pipeline.canonical_rank_score()` therefore combines the pre-signal editorial score and `signal_score` as `0.75 * editorial_pre_signal + 0.25 * signal` for the final period-ranking score.

## Critical finding: final-score compounding is prevented

The earlier hypothesis that the `0.30` signal injection is compounded again through the `0.75/0.25` final formula is **not correct**.

`_base_editorial_score()` checks `editorial_score_pre_signal` before `editorial_score`. Because `main._apply_signal_ranking()` stores the original editorial score in `editorial_score_pre_signal`, the inflated intermediate value is not used by `canonical_rank_score()`.

Therefore the final ranking formula is effectively:

`final_editorial_score = 0.75 * editorial_score_pre_signal + 0.25 * signal_score`

and not:

`0.75 * (editorial_score_pre_signal + 0.30 * signal_score) + 0.25 * signal_score`.

## Critical finding: upstream cluster ordering uses the inflated score

A separate issue **is confirmed directly from the code**.

`main._apply_signal_ranking()` inflates `editorial_score` with `0.30 * signal_score`, and `main.py` subsequently sorts the editorial pool by that field before calling `gate_story_candidates()`.

`src/story_gate.py` then sorts each input pool using `editorial_score` and then `signal_score` after leader/protection fields. `src/story_identity.py` performs duplicate elimination in first-wins order: the first non-duplicate candidate is accepted and later duplicate candidates are rejected.

Consequently, the causal path is confirmed:

`inflated editorial_score` → `story_gate.rank()` ordering → `deduplicate_stories()` first-wins traversal → surviving story representative.

This is not a hypothesis. What remains empirical is the **frequency and magnitude** of representative changes on realistic candidate pairs.

The `story_gate.rank()` function also references `signal_score` immediately after the already signal-inflated `editorial_score`. Thus the same underlying signal can affect ordering twice at this upstream stage: once through the 0.30 injection into `editorial_score`, and once as the next ranking key.

## Direct feature overlap

The following concepts are independently represented in both editorial and signal layers:

| Concept | Editorial layer | Signal layer | Correlation risk |
|---|---|---|---|
| Freshness | `freshness` contribution | `freshness_score()` | High |
| Novelty | `novelty_score` | `novelty_score()` | High |
| Future impact | `future_relevance` | `future_impact_score()` | High |
| Evidence / credibility | `scientific_credibility` | `evidence_strength`, `source_quality` | Medium–High |
| Technical depth | editorial readiness metadata / classification | `technical_significance_score()` | Medium; semantics are not identical |
| Strategic relevance | strategic forecast can augment mission metadata | `strategic_relevance_score()` | Medium–High |
| Expert/leader influence | leader priority contribution | `expert_influence_score()` | High for leader items |
| Trend | convergence/topic classification | `trend_alignment_score()` | Medium |
| Source quality | source tier contributes to credibility | `source_quality_score()` | High |

## Protected-stream attribution

Leader/interview handling is partly policy metadata and partly scoring metadata. `src/editorial.py` can mark leader/interview state, while `signal_engine.expert_influence_score()` independently reads leader-related metadata. This requires explicit attribution rules before any scoring redesign.

## Golden dataset

`tests/fixtures/p1_golden_dataset.json` freezes 12 deterministic scenarios covering:

- core AI research
- expert interview
- quantum + AI convergence
- consciousness/cognition + AI
- BCI + AI
- embodied robotics
- bio/AI
- infrastructure/deployment
- future/risk/governance
- low-evidence community content
- quantum out-of-scope content
- major multimodal model release

The expected labels are qualitative and intentionally avoid prescribing new scores. P1 can therefore measure current behavior without silently redesigning the ranking model.

## Measurement harness

`tests/test_p1_story_gate_attribution.py` is an audit-only harness. It:

1. Runs the 12 fixtures through the real editorial and signal enrichers.
2. Reproduces the production `story_gate.rank()` key and a counterfactual key that uses `editorial_score_pre_signal` instead of the inflated `editorial_score`.
3. Applies a bounded deterministic perturbation grid to paired same-story variants.
4. Reports how many of the 12 cases are structurally sensitive to the inflated upstream score and how often the representative ordering changes under the counterfactual key.

The perturbation result is explicitly a **sensitivity measurement**, not a claim about production frequency. It must not be interpreted as evidence that all such changes occur in live traffic.

## Next measurements

Before changing behavior, P1 should calculate:

1. Pairwise feature correlation on the golden set after both enrichers run.
2. Marginal score contribution of each semantic concept before and after `_apply_signal_ranking()`.
3. Leader-specific contribution from editorial priority versus signal expert influence.
4. Sensitivity of `story_gate` representative selection to the inflated intermediate score.
5. Actual observed representative changes on a retained sample of real duplicate/near-duplicate clusters, when such a sample is available.
6. Ruff count on the same repository surface, using 21 as baseline.

No production scoring or policy behavior is changed by this audit branch.
