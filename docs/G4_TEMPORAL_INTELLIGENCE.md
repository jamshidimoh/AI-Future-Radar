# G4 — Temporal Intelligence

Status: IMPLEMENTED — VALIDATION PENDING

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

## Non-goals

G4 does not implement cross-domain convergence, scenario/foresight generation, or production shadow-mode integration.
