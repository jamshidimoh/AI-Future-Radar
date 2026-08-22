# Radar Golden Dataset Contract

## Purpose

The Golden Dataset is the acceptance benchmark for the Radar 2.0 migration. It prevents subjective claims that the new engine is better and provides a stable reference for editorial quality, selection quality and regression safety.

## Target size

Initial target: 100–200 real stories sampled from historical Radar discovery/production runs. The first set should intentionally include difficult and representative cases rather than only successful publications.

## Historical seed workflow

The repository contains `data/telegram_feedback.json`, which records real published-message metadata such as source, title, URL, content type and leader/watch-person fields. It does **not** contain reliable labels for rejected candidates, importance or relevance. Therefore it must not be treated as a Golden Dataset by itself.

`tools/build_golden_seed.py` converts this historical publication history into an annotation-ready JSONL queue. The builder deduplicates by canonical link, preserves the historical metadata and leaves judgment fields explicitly unset. A generated seed is evidence for annotation, not an acceptance benchmark.

The correct workflow is:

```text
historical production/feedback data
            |
            v
     annotation-ready seed
            |
            v
human editorial annotation
            |
            v
   labeled Golden Dataset
            |
            v
   old-vs-new evaluation
```

The seed builder intentionally avoids inventing labels from the fact that an item was previously published.

## Required case classes

The dataset should contain examples of:

- major model releases,
- major research breakthroughs,
- substantive interviews and podcasts,
- leader activity that is genuinely important,
- leader mentions that are not editorially important,
- future/AGI forecasts,
- AI safety/governance developments,
- quantum/AI intersections,
- AI + genetics/biology,
- mind/consciousness + AI,
- important official announcements,
- multi-source stories,
- near-duplicate stories,
- repeated/saturated topics,
- weak/low-signal content,
- misleading headlines or poor-source candidates.

## Annotation contract

Each case should capture, when knowable from the historical record:

```text
case_id
source_items[]
canonical_story_id
should_publish
importance_band
relevance_band
best_source
expected_story_group
is_duplicate
leader_name (optional)
leader_relevance
is_substantive_interview
is_model_release
risk_level
minimum_evidence_level
expected_rank_band
expected_content_type
notes
```

## Evaluation dimensions

The old and new engines should be compared on the same cases.

Primary metrics:

1. **Story quality / relevance** — proportion of selected stories judged genuinely useful for the Radar mission.
2. **Leader-interview recall** — important substantive interviews retained in the candidate/selected set.
3. **Duplicate rate** — repeated stories selected or published.
4. **Evidence coverage** — major factual claims supported by the recorded evidence.
5. **Factual/attribution quality** — names, numbers, versions, dates and source attribution remain correct.
6. **Diversity** — avoidance of repeated people, companies, topics and content types in one editorial portfolio.
7. **Freshness/novelty** — preference for genuinely new developments rather than previously saturated stories.
8. **Publication integrity** — required title, summary, why-it-matters, source link and ChatGPT link survive the formatting/delivery path.
9. **Latency** — bounded processing time for a representative input set.

## Acceptance policy

A new component must not replace the current production component solely because its unit tests pass.

A migration stage is accepted only when:

- critical regression tests pass,
- Golden Dataset performance is not materially worse on protected dimensions,
- the intended quality dimensions improve or remain stable,
- latency stays within the production budget,
- publication integrity is preserved.

The exact thresholds should be set after the first baseline run rather than invented in advance.

## Evaluation modes

### Offline

Run both engines on identical historical cases with network/LLM behavior controlled where possible.

### Shadow

Run the new engine beside production without publishing its decisions. Compare outputs and reasons.

### Canary

Allow the new engine to publish only a controlled subset after offline and shadow acceptance.

### Full cutover

Switch the production default only after canary results remain within the acceptance thresholds.

## Data integrity

The dataset must not contain secrets, API keys or personal credentials. Source URLs and public publication metadata are sufficient for most benchmark cases.