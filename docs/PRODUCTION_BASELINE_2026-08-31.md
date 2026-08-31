# AI Future Radar — Production Baseline

**Baseline date:** 2026-08-31
**Baseline branch:** `main`
**Baseline revision:** `67720ce812803b6bdb6389a145d75a0daeedae56`
**Baseline status:** FROZEN

## Decision

The current `main` branch is the production-news baseline. No new Trend Intelligence, Foresight, or experimental architecture work should be committed directly to `main`.

All future evolution work starts from the baseline revision and proceeds on a dedicated `evolution/*` branch. Promotion to `main` requires explicit acceptance evidence.

## Evidence available for the baseline

- PR #72 (strict mission relevance hardening) was merged after the complete pre-merge quality and production gates passed.
- Post-merge quality validation on the documentation baseline passed: compile, production imports, configuration validation, Ruff changed-surface gate, and the full quality contract suite.
- Production Quality and Final Production Acceptance had passed on the validated PR head before merge.
- Legacy PRs #67, #68 and #71 were closed and are not part of the current production path.

## Freeze rules

1. Do not add experimental Trend Intelligence logic directly to `main`.
2. Do not weaken or delete production tests to obtain green CI.
3. Do not merge a stale branch solely because it contains useful code.
4. Every evolution gate must have tests and revision-specific evidence.
5. Production publication quota, protected streams, source exclusions, fail-closed behavior and editorial gates remain authoritative.
6. Trend Intelligence must remain publication-decoupled until controlled integration is explicitly accepted.

## Important limitation

The baseline is a production news radar with hard relevance/quality safeguards. It is **not yet** a complete longitudinal Technology Intelligence / Foresight system. Full completion requires G1 through G9 below.

## Source of truth

This document records the engineering decision to freeze the production baseline. The evolution roadmap is maintained in `docs/EVOLUTION_V1_PLAN.md`.
