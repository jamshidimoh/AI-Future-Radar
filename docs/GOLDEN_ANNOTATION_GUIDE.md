# Golden Dataset Annotation Guide

Status: READY FOR HUMAN ANNOTATION

This guide defines the labeling protocol for the 200-record historical annotation seed produced by `tools/build_golden_seed.py`. It is intentionally independent of the current Radar publication decisions. Historical `published` status is not treated as ground truth.

## 1. Annotation objective

Create a small, auditable gold dataset for offline comparison of the current Radar baseline against MSA V1. Labels must represent the annotator's judgment from the available source material, not what the historical pipeline previously published.

## 2. Required labels

Each record must receive:

- `canonical_story_id`: stable ID shared by records that describe the same underlying story/event.
- `should_publish`: `true` or `false` under the Radar editorial scope.
- `importance_band`: `high`, `medium`, or `low`.
- `relevance_band`: `high`, `medium`, or `low`.
- `best_source`: URL or source identifier judged strongest for the claim.
- `expected_story_group`: human-defined canonical story group.
- `is_duplicate`: `true` when the record is a duplicate/repost of another record in the corpus.
- `leader_relevance`: `high`, `medium`, `low`, or `none` for substantive leader/interview relevance.
- `is_substantive_interview`: `true` or `false`.
- `is_model_release`: `true` or `false`.
- `risk_level`: `low`, `medium`, `high`, or `critical` when applicable.
- `minimum_evidence_level`: `OBSERVED`, `SUPPORTED`, `CORROBORATED`, `INFERRED`, or `HYPOTHESIS`.
- `expected_rank_band`: `top`, `middle`, or `bottom` among publishable records for the evaluation slice.
- `expected_content_type`: one of the repository's controlled content types.
- `notes`: concise evidence-based rationale.

## 3. Labeling rules

### Identity and duplicates

Group by underlying event or claim, not wording. A new title, translation, repost, or lightly edited copy remains the same story when the underlying event is unchanged. New independent evidence about an old story should remain linked to the same canonical story while being marked as new evidence in the notes.

### Publication

`should_publish=true` only when the item is inside the Radar's editorial scope and has sufficient evidence for publication. Popularity, repost count, or historical publication must never be used as the sole reason.

### Importance

High importance means the event could materially affect AI/advanced technology, infrastructure, research direction, human cognition, robotics, quantum, BCI/bio-AI, governance, industry structure, or future-of-work trajectories. Importance is independent from confidence.

### Relevance

High relevance means the item directly fits the Radar's scope. Medium means useful but secondary. Low means peripheral or weakly connected. Out-of-scope items should normally be `should_publish=false`.

### Evidence

Use the strongest evidence actually available in the record. Do not upgrade evidence because the source is famous. Distinguish direct observation from inference.

### Interviews and leaders

`is_substantive_interview=true` only when the source contains meaningful original statements, analysis, or technical discussion by the identified person. A headline mentioning a leader is not sufficient.

### Model releases

Use `is_model_release=true` for a substantive model/system release or availability event, not ordinary commentary about models.

### Risk

Risk describes potential systemic or operational consequence, not sensationalism. Use `critical` sparingly and only when the evidence supports a severe consequence.

## 4. Adjudication protocol

Prefer two independent annotators. They should label independently before seeing each other's decisions. Disagreements should be resolved by a third reviewer or explicit adjudication pass.

At minimum, calculate agreement for `should_publish`, `is_duplicate`, `importance_band`, and `relevance_band`. Record unresolved disagreements rather than silently choosing a label.

## 5. Quality controls

Before the gold dataset is accepted:

1. Every record has all required labels.
2. Boolean fields contain only booleans.
3. Controlled-vocabulary fields contain only permitted values.
4. Duplicate groups are internally consistent.
5. `is_duplicate=true` records point to an existing canonical story group.
6. `should_publish` decisions include a rationale in `notes`.
7. No label is copied from the historical pipeline merely because it was previously published.
8. Annotation provenance is recorded, including annotator and adjudication status where available.

## 6. Evaluation gate

The historical benchmark remains blocked until `data/golden_dataset.jsonl` exists and passes schema validation. The benchmark must then compare Baseline and MSA V1 on the same frozen corpus and report quality, duplicate handling, evidence coverage, relevance, ranking, and publication integrity separately.

Aggregate score alone cannot produce acceptance. Critical safety/editorial invariants remain mandatory.

## 7. Non-negotiable boundary

A seed file is not a gold dataset. Automated structural tests are not empirical superiority evidence. No synthetic labels may be promoted to gold labels merely to make the benchmark pass.
