# G1 — Deterministic Signal and Trend Engine

Status: IMPLEMENTED — VALIDATION PENDING

## Scope

G1 adds a publication-decoupled current-window trend engine. It consumes normalized story records that already contain signal information and detects reproducible clusters. It does not publish, alter editorial eligibility, modify source authority, or create persistent lineage.

## Input contract

Each item may provide:

- `id` or `story_id`
- `title`, with optional `summary`, `description`, and `category`
- `signal_score` in the existing 0–100 scale, or a numeric `signal_vector`
- source identity through `source_id`, `source`, `source_name`, or `publisher`
- optional novelty through `signal_vector.novelty` or `novelty`

Missing optional values are handled deterministically; invalid configuration fails closed.

## Deterministic clustering

Similarity is Jaccard similarity over normalized title/summary/description/category tokens. The configured threshold defaults to `0.45`.

Clustering uses complete-link behavior: a cluster may merge only when every cross-pair between the two candidate clusters clears the threshold. This prevents a transitive A–B–C chain from becoming a single trend when A and C are not directly similar enough.

Only clusters meeting `minimum_cluster_size` (default `2`) are emitted. Weak signals are retained as candidate trends; G1 does not impose an editorial publication floor.

## G1 output contract

Every emitted cluster contains:

- `cluster_id`: deterministic hash-based identifier for the current member set;
- `member_ids`: sorted stable member identifiers;
- `cluster_size`;
- `representative_id`: highest signal member with deterministic tie-breaking;
- `mean_signal_score`;
- `mean_novelty_score`;
- `coherence`: mean pairwise similarity;
- `source_independence`: distinct source ratio;
- `trend_score`: deterministic weighted aggregate distinct from `signal_score`;
- `trend_confidence` in `[0,1]`;
- `trend_class`: `candidate` or `high` according to configured confidence.

Source Tier is intentionally excluded from the G1 trend score. Source authority and evidence quality remain separate semantic dimensions for later gates.

## Configuration

`config/trend_engine.yaml` defines the similarity threshold, minimum cluster size, confidence boundary and score weights. The four score dimensions are:

- mean signal;
- cluster coherence;
- source independence;
- mean novelty.

Weights must be non-negative and sum to `1.0`.

## Non-goals

G1 does not provide persistent IDs across runs, merge/split lineage, evidence graphs, temporal acceleration, cross-domain convergence, or foresight. Those are G2–G6 responsibilities.

## Acceptance evidence

The G1 test suite covers deterministic repeatability, bounded similarity, complete-link anti-chain behavior, weak-signal retention, source-independence effects, separation from Source Tier, safe unclustered enrichment, and fail-closed configuration validation.

Production publication remains unchanged until a later controlled integration gate explicitly adopts the intelligence outputs.
