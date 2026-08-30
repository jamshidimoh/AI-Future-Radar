# G3 — Evidence Intelligence Gate

## Objective

Make evidence auditable without conflating source authority with scientific truth.

## Invariants

1. Supporting and counter-evidence remain separate.
2. Reposts sharing an independence group do not inflate independent-source count.
3. Evidence strength is bounded to `[0, 1]`.
4. Conflicting reuse of an evidence identifier fails closed.
5. The deterministic graph does not declare claims scientifically true.
6. `Source Tier`, `Evidence Level`, `Signal Score`, `Trend Score`, and `Forecast Confidence` remain separate dimensions.

## Acceptance evidence

G3 is not considered production-complete until unit tests, integration tests, and a real CI run pass on the same commit, followed by regression validation against the existing production invariants.

## Next gate

G4 adds temporal state transitions, acceleration/decay measures, and disconfirmation handling without changing evidence provenance.
