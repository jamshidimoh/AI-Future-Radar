# G5 — Cross-Domain Convergence Gate

## Objective

Detect higher-order convergence between independently tracked trends across distinct domains without assuming that semantic similarity alone proves a causal relationship.

## Protected domains

The engine explicitly supports first-class domain identifiers for AI, emerging technology, quantum, robotics, biotechnology, BCI, consciousness/cognition, philosophy of science, and futures/foresight.

## Invariants

1. A meta-trend requires at least two distinct domains.
2. Weak trends do not create a meta-trend merely because they are topically related.
3. Evidence count and trend score remain separate dimensions.
4. Cross-domain convergence is a hypothesis, not proof of causality.
5. The engine remains deterministic and publication-decoupled.

## Acceptance

G5 is not production-complete until tests and CI pass on the same commit and historical/shadow validation demonstrates that convergence does not create systematic false positives.
