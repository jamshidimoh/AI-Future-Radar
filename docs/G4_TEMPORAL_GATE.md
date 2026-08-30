# G4 — Temporal Intelligence Gate

## Objective

Track how a trend changes over time without treating short-lived media volume as durable evidence.

## States

`emerging`, `accelerating`, `established`, `stagnating`, `fading`, `disconfirmed`, `revived`.

## Deterministic signals

- Trend score delta between observations.
- Evidence-count delta.
- Independent-source count is preserved as a separate provenance dimension.
- Zero current evidence with zero current score may mark a trend `disconfirmed`.

## Acceptance rule

G4 is not production-complete until unit/integration tests and a real CI run pass on the same commit, followed by regression validation against existing production invariants.

The temporal engine does not alter evidence provenance and does not make scientific truth claims.
