# G7 — Shadow Mode and Measurement

Status: IMPLEMENTED — VALIDATION PENDING

G7 provides a measurement harness for the intelligence stack before controlled production integration.

## Measurements

The harness records determinism, trend/domain coverage, evidence volume, independent-source count, contradiction rate, temporal signal count, convergence strength, scenario count, and high-uncertainty scenario count.

Shadow comparisons reject candidates that lose deterministic reproducibility or exceed the configured contradiction-rate delta.

## Safety boundary

G7 is shadow-only. It does not publish, rank, reject, select, quota, or deliver messages. It is explicitly separated from Telegram and the editorial path.

## Non-goals

G7 does not authorize production changes. G8 is the controlled integration gate and must require an explicit feature flag plus rollback path.
