# G2 — Persistent Trend Registry and Lineage

Status: IMPLEMENTED — VALIDATION PENDING

G2 extends the validated G1 current-window trend engine with persistent identity and auditable lifecycle lineage. It is publication-decoupled and does not change editorial eligibility, ranking, quota, or Telegram publication.

## Identity

G1 cluster IDs are hashes of the current member set. That is useful for a deterministic snapshot but cannot remain stable when members are added or removed. G2 therefore maintains a persistent registry keyed by a stable `trend-g2-*` identity and reconciles new observations against previous member sets.

A previous cluster is eligible for identity retention when member overlap reaches the configured threshold and minimum shared-member count. Exact replays therefore retain the same identity across runs and process restarts.

## Persistence

The registry schema contains:

- `clusters`: durable trend identities and their latest state.
- `signal_history`: append-only observations with run ID, run index, members, score, confidence and state.
- `lineage`: deterministic lifecycle events.
- `last_run_id` and `last_run_index`: monotonic reconciliation watermark.

`save_registry` writes through a temporary file and atomic replacement so a completed write does not leave a partially written JSON document at the target path.

## Lineage

G2 records four lifecycle classes required by the roadmap:

- `merge`: multiple previous identities contribute to one current cluster; the strongest deterministic prior identity is retained.
- `split`: one previous identity contributes to several current clusters; one deterministic child retains the parent ID and other children receive new IDs linked to the parent.
- `decay` / `revival`: an unseen trend is marked decayed after the configured miss count; a later matching observation restores the same identity with state `revived`.
- `disconfirmation`: an explicit previous identity is terminally marked `disconfirmed`. A later matching observation cannot silently reuse it and instead receives a fresh identity linked with `reappeared_after_disconfirmation`.

## Replay and determinism

Input clusters are normalized by sorted member IDs before reconciliation. Matching, parent retention, merge selection, split ownership and lineage ordering are deterministic. Replayed observations do not manufacture a new trend identity.

The registry refuses non-monotonic `run_index` values. This prevents stale or replayed windows from silently overwriting the current registry watermark.

## End-to-end adapter

`src/trend_intelligence_v2.py` provides `run_current_window`, which runs G1 clustering, loads the G2 registry, reconciles identities and saves the updated registry. The adapter has no publication side effects and can therefore be exercised independently of production delivery.

## Acceptance evidence

G2 acceptance requires:

- stable identity across runs and restarts;
- duplicate/replayed signal protection;
- merge and split lineage reconstruction;
- decay and revival identity retention;
- terminal disconfirmation and explicit reappearance lineage;
- deterministic history/lineage reconstruction;
- valid persistence round-trip;
- full repository regression and production acceptance gates green on the immutable G2 revision.

G2 does not implement evidence graphs, temporal acceleration, cross-domain convergence, foresight, or controlled production integration. Those remain later gates in `docs/EVOLUTION_V1_PLAN.md`.
