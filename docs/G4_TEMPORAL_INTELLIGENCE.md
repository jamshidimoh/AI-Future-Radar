# G4 — Temporal Intelligence

Status: VALIDATION EVIDENCE RECORDED; FINAL REVISION VALIDATION REQUIRED

G4 consumes persisted G2 observations and derives deterministic temporal descriptors without changing publication behavior.

## Measures

- persistence ratio across the observed run span;
- overall and recent trend-score slope;
- acceleration as the change between recent and prior slope;
- weakening when recent slope crosses the configured negative threshold;
- transient spikes when a peak is not sustained;
- periodicity from deterministic autocorrelation over the active/decayed sequence;
- maximum observation gap.

## Contract

Observations are keyed by trend identity and ordered by monotonically increasing `run_index`. Duplicate run indexes fail closed. Output is deterministic and sorted by trend identity.

The default configuration is disabled and explicitly publication-decoupled. G4 is analytical telemetry for future intelligence layers, not an editorial ranking mechanism.

## Validation evidence

Workflow run `33599379736`, job `100149477982`, immutable G4 head `7b43e51e68c749ea34e1947c39df4cbb8b18653b`:

- full repository regression: 506 passed;
- G4 focused contract: 9 passed;
- frozen/final production acceptance tests: 12 passed;
- publication-decoupling contract: PASS.

This documentation update changes the branch SHA, so the new immutable head must be revalidated before G4 is declared complete.

## Non-goals

G4 does not implement cross-domain convergence, scenario/foresight generation, or production shadow-mode integration.
