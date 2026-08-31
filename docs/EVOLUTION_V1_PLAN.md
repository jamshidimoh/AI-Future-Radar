# AI Future Radar — Technology Intelligence Evolution v1

## Objective

Evolve the production news radar into an auditable Technology Intelligence and Foresight system without weakening the existing production publication contract.

## Current baseline

- Production branch: `main`
- Baseline revision: `67720ce812803b6bdb6389a145d75a0daeedae56`
- Evolution branch: `evolution/technology-intelligence-v1`
- Production baseline: frozen
- No direct experimental development on `main`

## Engineering principle

Build the intelligence layer incrementally. Each gate must be independently testable, observable, reversible, and evidence-backed. A later gate cannot be declared complete when an earlier gate is not accepted.

## Gate roadmap

### G1 — Deterministic Signal and Trend Engine

Deliver:
- normalized signal schema
- deterministic similarity and candidate clustering
- signal score independent from source tier
- weak-signal retention
- regression tests for deterministic repeatability

Exit evidence:
- unit and contract tests pass on one immutable revision
- repeated execution produces identical cluster assignments
- production publication behavior is unchanged

### G2 — Persistent Registry and Lineage

Deliver:
- stable cluster IDs across runs and restarts
- append-friendly signal history
- merge/split/revive/decay/disconfirmation lineage
- deterministic reconciliation

Exit evidence:
- persistence/restart tests pass
- lineage reconstruction succeeds
- duplicate/replayed signals do not create false new clusters

### G3 — Evidence Intelligence

Deliver:
- claim/evidence entities
- supporting vs counter-evidence separation
- evidence levels independent of source tier
- source-independence grouping
- provenance references

Exit evidence:
- same-source reposts cannot increase independence
- counter-evidence is retained
- evidence calculations are deterministic and auditable

### G4 — Temporal Intelligence

Deliver:
- longitudinal trend observations
- trend state machine
- acceleration/persistence measures
- fading/revival/disconfirmation behavior

Exit evidence:
- state is reproducible from persisted observations
- temporal tests cover monotonic and contradictory histories
- popularity spikes do not substitute for persistence evidence

### G5 — Cross-Domain Convergence

Deliver:
- explicit domain graph/link model
- minimum independent-domain criteria
- convergence score separate from trend score
- hypothesis semantics, not causal certainty

Required domains:
- AI
- advanced computing
- robotics
- quantum
- biotechnology/bio-AI
- brain-computer interfaces
- consciousness/cognition
- philosophy of science
- futures/foresight
- emerging technologies

Exit evidence:
- duplicate sources cannot fabricate convergence
- weak evidence cannot create high-confidence convergence
- cross-domain tests pass on the same revision

### G6 — Foresight Intelligence

Deliver:
- driver mapping
- uncertainty dimensions
- impact/risk/opportunity representation
- Three Horizons hooks
- scenario hooks
- explicit distinction between observation, inference and speculation

Exit evidence:
- forecasts retain uncertainty and assumptions
- evidence state is not overwritten by forecast interpretation
- deterministic provenance remains reconstructable

### G7 — Shadow Production

Deliver:
- historical/live shadow execution
- no publication side effects
- multi-run stability measurements
- false-cluster and missed-signal evaluation
- drift monitoring

Exit evidence:
- defined shadow window passes
- cluster identity stability is measured
- production publication metrics show zero regression

### G8 — Controlled Production Integration

Deliver:
- feature flag or equivalent isolation
- safe degradation
- rollback path
- controlled exposure of validated intelligence outputs

Exit evidence:
- disabled-mode behavior equals current production behavior
- failure containment is demonstrated
- rollback is tested
- production gates remain fail-closed

### G9 — Final Production Acceptance

Required:
- full regression and contract suite green
- production quality gates green
- evidence/provenance checks green
- shadow validation evidence present
- state/lineage validation present
- controlled integration validated
- rollback/failure containment validated
- architecture/operator documentation synchronized

Only G9 may change the project status to COMPLETE.

## Branch policy

`main` is the production baseline. Work-in-progress evolution belongs under `evolution/*`. A feature branch may merge only through a reviewed PR whose head revision has the required gate evidence.

## Anti-patterns prohibited

- merging stale branches because they contain useful code
- creating empty or documentation-only revisions solely to manufacture a sense of acceptance
- changing tests to hide regressions
- equating source prestige with evidence strength
- equating repetition with independent corroboration
- using LLM output as sole authority for provenance, cluster identity, scientific validity, or publication eligibility
- declaring a gate complete without revision-specific evidence

## Current state

The branch is the controlled starting point for G1. No claim is made that G1-G9 are complete merely because architecture documents or prototype modules exist elsewhere in repository history.
