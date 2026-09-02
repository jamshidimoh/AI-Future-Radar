# G8 — Controlled Production Integration

Status: IMPLEMENTED — VALIDATION PENDING

G8 introduces a side-effect-free bridge for the intelligence stack. The bridge creates an auditable proposal and evaluates explicit rollout gates; it does not call Telegram or mutate publication state.

## Rollout states

- `off`: no integration.
- `shadow`: observe and measure only.
- `controlled`: eligible to apply only when shadow measurement passes and `apply=true`.

Rollback is mandatory in every mode. Applying is prohibited outside `controlled` mode. The default repository policy is `shadow` with `apply=false`.

## Required gates

A controlled application proposal requires a stable candidate identity, a stable baseline identity, successful shadow measurement, explicit controlled mode, and explicit apply permission. Any failed gate produces an auditable reason and denies application.

## Safety boundary

The bridge is intentionally decoupled from publication side effects. No change is made to editorial ranking, selection, quotas, Telegram delivery, or existing production state.

Real production rollout still requires current production evidence and operational approval; this gate validates the software safety boundary, not business authorization.
