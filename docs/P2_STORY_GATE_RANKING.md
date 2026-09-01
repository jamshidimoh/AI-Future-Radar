# P2 Story-Gate Ranking Contract

## Problem

The production path previously used a signal-inflated `editorial_score` and then `signal_score` again inside story-gate ordering. Final period ranking already protected itself by preferring `editorial_score_pre_signal`, but the upstream representative decision did not.

## Contract

Story representative selection is now ranked by:

1. leader priority
2. leader source authority
3. protected-content priority
4. `editorial_score_pre_signal` (falling back to legacy `editorial_score` only when the pre-signal field is absent)
5. publication timestamp

`signal_score` is intentionally absent from this representative-ranking key.

After deduplication, the gate also materializes `final_editorial_score` as:

`0.75 * editorial_score_pre_signal + 0.25 * signal_score`

when the pre-signal field is available. This makes the main-path portfolio selector consume the same canonical final score that the period-ranked path expects.

## Scope

This is a targeted P2 architecture correction. No editorial feature weights were changed, and no mission-aware or protected-stream policy was removed.

## Validation target

Regression tests must demonstrate:

- representative ordering is invariant to signal inflation when pre-signal editorial quality is unchanged;
- final score is derived from pre-signal editorial score plus signal score;
- existing protected/leader priority semantics remain intact;
- full repository quality and production acceptance suites remain green.
