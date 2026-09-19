# TypeSafe semantic reranking

The production radar keeps hard publication policy in code and uses TypeSafe only as a bounded semantic judgment layer.

## Modes

- `off`: no TypeSafe API call and no ranking behavior change.
- `audit`: call TypeSafe for the canonical candidate window, record the proposed order, but keep the existing order.
- `active`: use TypeSafe to rerank only the canonical candidate window.

Set these environment variables in the runtime:

```text
TYPESAFE_API_KEY=...
AI_RADAR_TYPESAFE_RERANK_MODE=audit
AI_RADAR_TYPESAFE_RERANK_WEIGHT=0.20
```

For GitHub Actions, store `TYPESAFE_API_KEY` as an Actions secret. The production workflow should expose it to the process only when the integration is intentionally enabled.

The default is `off`, so adding the dependency does not change current production behavior.

## Ranking contract

The TypeSafe layer evaluates three independent dimensions:

1. mission fit
2. novelty / information gain
3. editorial value

These are combined into a semantic judgment score. Confidence attenuates that signal. The result is blended with the existing candidate order rather than raw editorial-score magnitudes, because the canonical score scale is owned by the existing radar pipeline.

TypeSafe never overrides source validation, deduplication, language gates, protected-lane rules, quotas, diversity controls, Telegram safety, or delivery policy.

## Rollout

Start with `audit` and compare proposed order against the existing order on representative production runs. Only switch to `active` after the audit shows useful changes without regressions in source diversity, protected stories, or publication gates.

The integration is fail-open: missing credentials or a TypeSafe API failure preserves the existing order.
