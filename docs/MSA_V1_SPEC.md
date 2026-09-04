# AI Future Tech Radar — MSA v1

Status: **V1 SPECIFICATION APPROVED FOR BENCHMARK**

This document defines the isolated vNext meta-signal layer. It does not modify the frozen production baseline on `main`, including the existing editorial prompt and ChatGPT navigation.

## 1. Objective

MSA adds source intelligence, evidence-aware convergence, signal typing, temporal evolution, systemic-risk interpretation, and explainable meta-ranking around the current Radar. It may discover, enrich, or reprioritize candidates; it does not automatically replace the baseline.

## 2. Canonical information chain

`Source → Post → Story → Event → Claim → Evidence → Signal → Future Horizon → Confidence → Priority → Editorial → Publication → Feedback`

Each layer has a single responsibility. Every production decision must be traceable backward through this chain.

## 3. Non-negotiable invariants

1. `Importance != Confidence`.
2. `Source Quality != Evidence Quality`.
3. `Post Count != Independent Evidence Count`.
4. `Repost Count != Independent Convergence`.
5. `Observed != Inferred`.
6. `Inferred != Confirmed`.
7. `Forecast != Fact`.
8. Correlation must not be promoted to causation without evidence.
9. High ranking never bypasses Evidence, Identity, or Editorial gates.
10. Provider failure must fail closed; no fabricated completion is allowed.
11. Popularity is metadata, not a direct quality signal.
12. The vNext layer must not silently alter the frozen baseline.

## 4. Source intelligence

Initial source scoring is a hypothesis for benchmarking, not ground truth:

`0.20 Reliability + 0.15 Evidence Quality + 0.15 Signal Quality + 0.10 Originality + 0.10 Future Relevance + 0.10 Domain Value + 0.10 Diversity Value + 0.10 Signal/Noise`

Source quality is time-aware and domain-aware. A low-quality source can still surface a valuable weak signal; low source quality reduces confidence rather than automatically deleting the signal.

## 5. Evidence model

Evidence states:

`OBSERVED | SUPPORTED | CORROBORATED | INFERRED | HYPOTHESIS | UNVERIFIED | CONTRADICTED`

Independent convergence is calculated from independent evidence clusters, not channel count. A repost graph should collapse to its underlying evidence origin whenever the relationship can be established.

## 6. Signal taxonomy

`S1 Research Breakthrough`
`S2 Emerging Technology`
`S3 Weak Signal`
`S4 Convergence Signal`
`S5 Systemic Risk`
`S6 Infrastructure Signal`
`S7 Paradigm Shift`
`S8 Capability Shift`
`S9 Industry Structure Shift`
`S10 Governance Shift`
`S11 Human/Cognitive Shift`
`S12 Societal/Work Transformation`

A candidate may have multiple signal labels, but the evidence supporting each label must remain traceable.

## 7. Systemic risk levels

`L1 Temporal Correlation`
`L2 Structural Plausibility`
`L3 Confirmed Dependency`

L1 never implies L3. A shared cause must remain a hypothesis until independently supported.

## 8. Future horizons

`H1 = 0–2 years`
`H2 = 2–5 years`
`H3 = 5+ years`

Horizon is a forecast dimension and must not be presented as an observed fact.

## 9. Meta-ranking

Initial benchmark formula:

`Priority = 0.15 Relevance + 0.15 Future Impact + 0.12 Novelty + 0.12 Independent Convergence + 0.10 Signal Strength + 0.10 Evidence Quality + 0.08 Systemic Importance + 0.06 Source Quality + 0.05 Momentum + 0.07 Blind-Spot Value`

All weights are calibration hypotheses. Benchmark results may support, revise, or reject them.

## 10. Decision matrix

| Importance | Confidence | Default action |
|---|---|---|
| High | High | Publish candidate |
| High | Low | Watch / verify |
| Low | High | Low priority |
| Low | Low | Drop |

Editorial gates remain authoritative.

## 11. Temporal signal evolution

A recurring phenomenon is represented as one Story with multiple Events and evidence updates. The system must distinguish:

`same story + new evidence → update`

`same story + different event → new event`

`different phenomenon → new story`

Signals may evolve from `Weak Signal` to `Corroborated` to `Convergence Signal` without losing their original provenance.

## 12. Blind-spot classes

`SOURCE_GAP`
`TAXONOMY_GAP`
`RECALL_GAP`
`CONVERGENCE_GAP`
`EVIDENCE_GAP`
`RANKING_GAP`
`TIMING_GAP`
`SYSTEMIC_GAP`

Missed signals are retained for offline diagnosis rather than silently discarded.

## 13. Feedback governance

`Production → Benchmark → Miss Analysis → Hypothesis → Offline Experiment → Adversarial Test → Expert Review → Regression → Candidate Version → Production`

Feedback cannot directly mutate production weights or prompts.

## 14. Benchmark acceptance

MSA V1 is accepted only if it demonstrates measurable value over the frozen baseline without unacceptable regression in precision, safety, duplication, evidence integrity, or operational reliability.

Minimum evidence required:

- common benchmark corpus
- baseline measurements
- MSA measurements
- adversarial cases
- explainability/traceability checks
- regression checks
- explicit comparison of value gained versus complexity added

No claim of empirical superiority is valid before this benchmark.
