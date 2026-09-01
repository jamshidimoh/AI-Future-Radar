# P3 Scoring Architecture

## Objective

Separate editorial publication value from technology-signal strength and prevent the same concepts from being scored twice under different names.

## Contracts

Editorial score measures publication suitability: mission fit, source authority, evidence confidence, publication value, and freshness.

Signal score measures technology-signal strength. It remains available as a distinct diagnostic/ranking input and does not redefine editorial suitability.

The final ranking layer combines the two canonical scores once. Story representative selection must use the pre-signal editorial score and never the signal score.

## Evidence boundary

P3 uses deterministic feature functions already available in the repository. The weights are an explicit policy candidate, not a claim of human-optimal ranking until evaluated on annotated data.

## Acceptance

The P3 branch must demonstrate:

- no signal feature is silently injected into the editorial score;
- canonical final score is computed exactly once;
- representative selection is invariant to signal inflation when editorial quality is unchanged;
- existing mission, leader, deduplication, and publication contracts remain green;
- the Ruff baseline remains attributable to pre-existing repository diagnostics.
