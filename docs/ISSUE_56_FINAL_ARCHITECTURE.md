# Issue #56 — Final Publication Architecture

## Product goal

AI Future Radar has one publication path:

`Story -> Editorial Policy -> Publication Orchestrator -> Telegram Transport -> confirmed DeliveryOutcome -> Ledger`

The production entrypoint is an application composition root. It may provide policy, rendering, transport and persistence adapters, but it must not implement a second publication protocol.

## Invariants

1. Policy rejection, duplicate detection and policy blocks never call Telegram.
2. Telegram transport is the only component that talks to Telegram.
3. A successful publication requires a real Telegram `message_id`.
4. Ledger persistence happens only after confirmed delivery.
5. Retryable and permanent transport failures are represented by `DeliveryOutcome` and never create a published Ledger entry.
6. There is one orchestrator and one delivery boundary; compatibility facades may exist only at legacy import boundaries and must not orchestrate.
7. `production_entrypoint.py` contains composition and run-level concerns only.

## Migration completion criteria

- `publication_orchestrator.publish_story()` is the production publication boundary.
- `production_entrypoint.py` delegates publication to that boundary rather than implementing delivery/ledger sequencing itself.
- Existing editorial selection, summarization, formatting and cadence policies remain behaviorally unchanged.
- Contract and regression tests pass.
- CI passes before merge.
- Issue #56 is closed only after the production path and acceptance tests prove the invariants above.

## Non-goals

No new ranking algorithm, source collector, Telegram feature, or editorial-policy redesign is part of this migration.
