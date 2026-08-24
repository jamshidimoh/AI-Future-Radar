# Issue #56 migration boundary

The production publication path is being consolidated into one explicit boundary:

`Story -> policy -> DeliveryOutcome -> Telegram delivery -> Ledger`

The orchestrator in `src/publication_orchestrator.py` owns the control flow. Policy rejection, duplicate detection, and policy blocks stop before transport. Delivery failures stop before the ledger. A ledger write is permitted only after a `DELIVERED` outcome contains a confirmed `message_id`.

This branch is an incremental migration foundation. The next step is to route `production_entrypoint.py` through this boundary and retire the remaining compatibility publication paths without changing Story/Dedup semantics.
