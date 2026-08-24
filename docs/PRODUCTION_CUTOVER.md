# Production cutover

This migration is complete only when `production_entrypoint.py` uses `src.production_publication_adapter.publish_production_story()` for publication and no longer performs Telegram/Ledger sequencing itself.

The adapter is intentionally thin: policy is supplied by the existing editorial logic, transport is supplied by the existing Telegram transport, and Ledger is called only by the publication orchestrator after a confirmed `message_id`.

Do not add a second publication path. Do not add compatibility logic to the orchestrator. Legacy modules may remain import-compatible but must delegate to the canonical boundary.
