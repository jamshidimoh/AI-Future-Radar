# TypeSafe semantic reranking

The production radar keeps hard publication policy in code and uses TypeSafe only as a bounded semantic judgment layer.

## Modes

- `off`: no TypeSafe API call and no ranking behavior change.
- `audit`: call TypeSafe for the canonical candidate window, record the proposed order, but keep the existing order.
- `active`: use TypeSafe to rerank only the canonical candidate window.

Runtime configuration:

```text
TYPESAFE_API_KEY=...
AI_RADAR_TYPESAFE_RERANK_MODE=active
AI_RADAR_TYPESAFE_RERANK_WEIGHT=0.20
```

The GitHub Actions production workflow provides the TypeSafe secret only to the production ranking process. The repository-level `.env.example` default remains `off`.

## Ranking contract

The TypeSafe layer evaluates three independent dimensions:

1. mission fit
2. novelty / information gain
3. editorial value

These are combined into a semantic judgment score. Confidence attenuates that signal. The result is blended with the existing candidate order rather than raw editorial-score magnitudes, because the canonical score scale is owned by the existing radar pipeline.

TypeSafe never overrides source validation, deduplication, language gates, protected-lane rules, quotas, diversity controls, Telegram safety, or delivery policy.

Only the bounded canonical candidate window is eligible. Replacement-buffer candidates outside that window remain untouched. Protected/Tier-0, technical-trend, mind, and voices/perspectives positions are excluded from semantic reranking.

## Live validation

A GitHub Actions live audit completed successfully on 2026-09-19 with six representative candidates and a real `TYPESAFE_API_KEY`. TypeSafe returned valid judgment and confidence values for every candidate.

Observed semantic scores from the second audit run:

- Frontier AI agents: score 0.4771, confidence 0.7100
- Generic AI productivity roundup: score 0.1830, confidence 0.7533
- BCI language decoding: score 0.5350, confidence 0.6800
- Quantum hardware milestone: score 0.3712, confidence 0.6367
- Robotics physical-world reasoning: score 0.3915, confidence 0.6667
- Familiar AI news recap: score 0.1995, confidence 0.7233

Dimension-level judgments were also returned and showed the intended separation between mission-relevant substantive items and generic roundups. This audit used synthetic representative candidates; it is evidence of the live semantic API path, not a claim that production ordering has already improved on historical traffic.

## Production rollout

The live audit passed, the full PR regression/acceptance gates passed, and the production workflow is now configured for `active` mode at weight `0.20`.

The rollout remains bounded and fail-open: missing credentials or TypeSafe/API errors preserve the existing order, and hard publication policy remains authoritative in code.

## Evidence

Live audit run:
https://github.com/jamshidimoh/AI-Future-Radar/actions/runs/35423857216

Pull request:
https://github.com/jamshidimoh/AI-Future-Radar/pull/139
