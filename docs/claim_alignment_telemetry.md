# Claim-to-Source Verification and Rejection Telemetry

## Scope

This change is additive. It does not alter quotas, ranking, production closure, publication acceptance, or the existing editorial quality contract.

## Pipeline position

`discovery -> canonical/dedup -> relevance -> clustering -> ranking -> selection -> summarization/repair -> editorial_value_ok -> claim_alignment -> final publication contract`

Claim alignment is initially **shadow-only**. A verifier result must never block publication in v1. Provider timeout, quota exhaustion, invalid JSON, or other verifier failures are recorded separately from semantic claim failures.

## Claim classes

The deterministic pre-check identifies these risk classes:

- `numeric`
- `date`
- `named_entity`
- `model_version`
- `benchmark`
- `comparison`
- `superlative`
- `causal`
- `attribution`
- `quote`

The semantic verifier may return `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, or `NOT_APPLICABLE` per claim.

## Reason codes

`numeric_mismatch`, `numeric_unit_mismatch`, `date_mismatch`, `unsupported_named_entity`, `unsupported_model_version`, `unsupported_benchmark`, `unsupported_comparison`, `unsupported_superlative`, `causal_overreach`, `unsupported_attribution`, `unsupported_quote`, `temporal_mismatch`, `insufficient_source_evidence`, `semantic_entailment_failure`, `verifier_provider_failure`, `verifier_timeout`.

## Rejection event schema

Each event is JSONL with `schema_version: rejection-event.v1` and contains run/item identity, stage, decision, reason code, optional ranking metadata, and structured details. The emitter is fail-safe and cannot affect the production path.

## Initial observability target

The next integration step should instrument existing decision points rather than duplicate them. Existing `ranking_audit` remains unchanged. Rejection telemetry is a separate audit stream for stage transitions and reasons.
