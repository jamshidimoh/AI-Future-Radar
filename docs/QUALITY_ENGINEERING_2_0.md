# AI Future Radar — Quality Engineering 2.0

## Purpose

This document defines the quality architecture for AI Future Radar. It replaces reactive rule-by-rule tuning with measurable regression control, production replay, and controlled rollout.

## Non-negotiable principles

1. Production behavior is changed incrementally.
2. A test must encode an editorial contract, not an arbitrary score threshold.
3. Mission relevance and publishability are separate decisions.
4. Discovery must preserve recall; ranking must optimize editorial value.
5. Deduplication and story identity are independent quality dimensions.
6. Diversity is a portfolio constraint, not a cosmetic penalty.
7. Production changes require offline regression evidence before merge.
8. Shadow/canary validation precedes high-risk editorial changes.
9. Every production failure becomes a reproducible regression case after review.
10. No final-status claim is made from CI alone; real production output must be audited.

## Target decision pipeline

```text
Sources
  -> Discovery
  -> Normalization
  -> Source/Evidence assessment
  -> Candidate generation
  -> Story identity / clustering
  -> Mission relevance
  -> Editorial classification
  -> Editorial scoring
  -> Reranking
  -> Diversity-constrained portfolio
  -> QA / safety
  -> Publication
  -> Production audit
  -> Evaluation / feedback
```

## Editorial classes

Every candidate should eventually map to one primary class:

- FRONTIER
- SCIENTIFIC
- STRATEGIC
- INTERVIEW_SIGNAL
- ROUTINE_PRODUCT
- GENERIC_APPLICATION
- IRRELEVANT
- LOW_EVIDENCE

Routine product classification must be semantic/conceptual where possible. It must not depend solely on English keywords because production titles can be translated into Persian before final editorial evaluation.

## Score dimensions

Mission relevance, novelty, evidence strength, technical/scientific depth, future impact, strategic significance, source quality, and audience value should remain separable dimensions. Routine/product, marketing, generic productivity, weak evidence, and commodity-signal penalties should not be hidden inside mission relevance.

## Golden benchmark

The benchmark is divided into:

- Development set: editable during engineering.
- Frozen regression set: changes require explicit review.
- Production failure set: real failures captured from audited runs.

The first target is 150–250 annotated cases, balanced across strong signals, borderline cases, routine applications, irrelevant material, duplicates, interviews, and frontier/scientific domains. Both English and Persian representations must be included.

## Core metrics

- Editorial precision: target >= 90% initially, then >= 95%.
- Important-signal recall: target >= 90%.
- Routine leakage: target 0% on the frozen set and near-zero in audited production.
- Exact/semantic duplicate rate: target 0%.
- Source and topic concentration: bounded by portfolio policy when sufficient candidates exist.
- Production delivery success: 100% for accepted messages.
- Education contract success: >= 95%.

No single metric may be optimized at the expense of important-signal recall.

## Evaluation layers

### PR gate

Fast deterministic checks, unit tests, contract tests, and frozen Golden Replay.

### Pre-production gate

Production replay, diversity checks, dedup checks, and representative editorial benchmark.

### Production validation

Shadow comparison, controlled canary, actual Telegram delivery audit, state audit, and rollback readiness.

## Change protocol

```text
Observed failure
 -> reproduce
 -> classify root cause
 -> add regression case
 -> implement smallest architectural fix
 -> run benchmark
 -> compare against baseline
 -> shadow production
 -> canary
 -> merge/promote
```

A one-off failure must not automatically generate a one-off keyword rule.

## Architecture evolution

`mission_selector.py` should be decomposed incrementally into clear responsibilities such as mission relevance, source/evidence assessment, editorial classification, novelty/story identity, portfolio optimization, and quality contracts. A full rewrite is prohibited until benchmark evidence demonstrates that extraction cannot safely achieve the required behavior.

## Production stability

Scheduler, Telegram delivery, state persistence, education, and deduplication must remain isolated from editorial experiments. Changes to one subsystem should not be bundled with unrelated changes.

## Definition of stable release

A release is considered production-stable only after the relevant CI contracts pass and at least 10 consecutive audited production cycles show no unexplained regression, zero duplicate leakage, zero routine leakage, successful delivery/state persistence, acceptable diversity, and important-signal recall at or above target.
