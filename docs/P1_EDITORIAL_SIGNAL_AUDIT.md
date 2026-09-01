# P1 Editorial/Signal Correlation Audit — Baseline

Date: 2026-09-01
Branch: `audit/p1-editorial-signal-golden`
Behavior changes: none

## Baseline

P0 Ruff repository audit baseline: **21 diagnostics**. This count is recorded in PR #78 and is the comparison point for P1.

## Current data flow

The production path is:

1. `editorial_clean.enrich_items()` computes editorial features and `editorial_score`.
2. `signal_engine.enrich_signal_items()` computes a separate signal vector and `signal_score`.
3. `main._apply_signal_ranking()` adds `signal_score * 0.30` back into `editorial_score`.
4. `unified_editorial_selection.select_regular_portfolio()` ranks candidates using the resulting editorial score, then applies policy constraints.
5. `period_ranked_pipeline.canonical_rank_score()` later combines editorial and signal values again for the period-ranking layer using 0.75/0.25.

## Direct feature overlap

The following concepts are independently represented in both editorial and signal layers:

| Concept | Editorial layer | Signal layer | Correlation risk |
|---|---|---|---|
| Freshness | `fresh` → `freshness` contribution | `freshness_score()` | High |
| Novelty | `novel` → `novelty_score` | `novelty_score()` | High |
| Future impact | `future` / `future_relevance` | `future_impact_score()` | High |
| Evidence / credibility | `scientific_credibility`, `cred` | `evidence_strength`, `source_quality` | Medium–High |
| Technical depth | `technological_readiness` is present in editorial scoring | `technical_significance_score()` | Medium; semantics are not equivalent |
| Strategic relevance | `mission_score` can be augmented by strategic forecast logic | `strategic_relevance_score()` | Medium–High |
| Expert/leader influence | leader priority contribution | `expert_influence_score()` | High for leader items |
| Trend | `cross_domain_convergence` / topic family indirectly | `trend_alignment_score()` | Medium |
| Source quality | `scientific_credibility` includes source tier | `source_quality_score()` | High |

## Compounding paths

The strongest architectural risk is not duplicate field names alone. It is repeated use of the same semantic evidence at multiple stages:

- Editorial computes a freshness/novelty/future-impact composite.
- Signal computes another freshness/novelty/future-impact composite.
- `main.py` adds 30% of the signal score to the editorial score.
- `period_ranked_pipeline.py` then derives a canonical rank score from editorial and signal components again.

This creates a plausible double-counting path even though the code deliberately documents signal metadata as independent of protected-stream bonuses.

## Protected-stream observation

Leader/interview handling is partly policy metadata and partly scoring metadata. `src/editorial.py` can mark leader/interview state, while `signal_engine.expert_influence_score()` can independently raise influence for the same leader-watch metadata. This requires an explicit attribution rule in P1 before any scoring change is made.

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

The expected labels are qualitative and intentionally avoid prescribing new scores. P1 can therefore compare current behavior with a frozen input/output expectation without silently redesigning the ranking model.

## Next audit measurements

Before changing behavior, P1 should calculate:

1. Pairwise feature correlation on the golden set after both enrichers run.
2. Marginal score contribution of each semantic concept before and after `_apply_signal_ranking()`.
3. Leader-specific contribution from editorial priority versus signal expert influence.
4. Whether `period_ranked_pipeline.canonical_rank_score()` compounds a previously injected signal contribution.
5. Ruff count on the same repository surface, using 21 as baseline.

No production scoring or policy behavior is changed by this commit.
