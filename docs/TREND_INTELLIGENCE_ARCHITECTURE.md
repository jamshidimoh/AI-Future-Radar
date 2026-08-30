# AI Future Radar — Trend Intelligence Architecture

## 1. Decision

The Radar evolves from story selection toward continuous technology intelligence. The production news pipeline remains fail-closed and its frozen acceptance invariants remain authoritative. Trend Intelligence is introduced behind a separate evolution boundary and is allowed to mature without changing publication quota or production safety contracts.

## 2. Advisory council model

The project uses a multidisciplinary internal advisory council model. It is a structured set of expert lenses, not a claim that external individuals have reviewed the repository.

Roles:

1. AI/ML and frontier-model analyst — model capability, agents, multimodality, scaling and evaluation.
2. Software/agentic engineering analyst — developer workflows, agent orchestration, reliability and production engineering.
3. Information retrieval/NLP analyst — entity resolution, semantic similarity, clustering, deduplication and temporal retrieval.
4. Science-methodology analyst — evidence hierarchy, replication, causal claims, uncertainty and source provenance.
5. Consciousness/cognition analyst — neuroscience, cognitive science, philosophy of mind and AI-consciousness claims; separates empirical results from philosophical argument.
6. Philosophy-of-science analyst — paradigm shifts, theory status, falsifiability, explanatory scope and scientific controversy.
7. Futures/foresight analyst — weak signals, horizon scanning, trend/driver distinction, Three Horizons, scenarios and uncertainty.
8. Emerging-technology strategist — technology readiness, adoption, economics, ecosystem effects and cross-domain convergence.
9. Data/reliability architect — state, lineage, idempotency, observability, deterministic contracts and concurrency.
10. Editorial/evidence governance analyst — publication policy, claims, quotations, counter-evidence, uncertainty labels and Persian RTL rendering.

## 3. Core distinction

The Radar must keep these dimensions separate:

- `source_tier`: discovery authority / provenance quality.
- `evidence_level`: strength and independence of evidence for a claim.
- `signal_score`: importance of an individual signal.
- `trend_score`: strength and maturity of a cluster over time.
- `forecast_confidence`: confidence in a forward-looking interpretation.

A Tier-1 interview can therefore be a high-value discovery signal while still requiring independent verification.

## 4. Signal lifecycle

```text
Discovery
  -> Canonicalization
  -> Entity / Topic Resolution
  -> Signal Qualification
  -> Evidence Annotation
  -> Candidate Clustering
  -> Cluster Validation
  -> Temporal Tracking
  -> Trend State
  -> Driver Mapping
  -> Cross-domain Convergence
  -> Foresight / Impact Assessment
  -> Editorial Surface
```

## 5. Trend Cluster contract

A cluster is not merely a group of semantically similar stories. It must have a persistent identity and an auditable history.

Required fields:

- stable `cluster_id`
- title and concise hypothesis
- domains / mission areas
- first_seen / last_seen
- signal_count
- independent_source_count
- source_tier distribution
- evidence distribution
- supporting evidence references
- counter-evidence references
- signal acceleration
- cross-domain convergence
- novelty / recency
- trend state: `weak_signal`, `emerging`, `accelerating`, `established`, `fading`, `disconfirmed`
- trend score
- uncertainty
- forecast confidence
- linked drivers / parent clusters
- provenance and update history

## 6. Clustering policy

Semantic similarity is necessary but insufficient. A cluster should be strengthened by independent sources, temporal persistence, cross-domain convergence and evidence diversity. Repetition from the same publisher or syndication network must not create artificial confidence.

Popularity is not a proxy for emergence. The system must retain low-popularity/high-novelty signals so that weak signals can form clusters before mainstream attention.

Cluster operations are:

- create
- attach signal
- reject attachment
- merge
- split
- decay
- revive
- disconfirm
- archive

Every operation must be auditable.

## 7. Foresight layer

The futures layer treats a trend as an observed or emerging pattern, not as a deterministic prediction. A trend becomes strategically important when it acts as a driver on the Radar mission.

For mature clusters, the Radar should support:

- origin-point analysis
- driver mapping
- Three Horizons positioning
- impact / uncertainty matrix
- plausible implications
- opportunity / risk tags
- research gaps
- scenario hooks

No scenario or forecast is allowed to overwrite the underlying evidence state.

## 8. Domain coverage

Trend clustering is explicitly enabled for:

- AI and advanced computing
- robotics and autonomous systems
- quantum technologies
- biotechnology / synthetic biology
- brain-computer interfaces
- consciousness / cognition
- philosophy of science
- futures / foresight
- digital transformation
- other emerging technologies with a defensible technology link

The existing AI-first publication policy remains a publication constraint. A cluster can be tracked even when it is not eligible for normal publication; publication eligibility remains governed by the production contract.

## 9. Evidence governance

Claims must retain provenance. The system should distinguish:

- primary research / official technical evidence
- institutional / standards evidence
- expert testimony / long-form interview
- high-quality secondary analysis
- community discovery
- speculation / opinion

Counter-evidence is first-class data. A cluster with strong supporting volume but strong contradictory evidence must not receive an inflated confidence score.

## 10. Architecture boundary

Trend Intelligence must not bypass:

- canonical story deduplication
- AI relevance / mission policy
- source exclusion
- quality and evidence gates
- Telegram publication contract
- persistent delivery state

The first implementation is deterministic and dependency-light. LLMs may later enrich cluster labels and hypotheses, but the LLM cannot be the sole authority for cluster identity, evidence strength or publication eligibility.

## 11. Acceptance criteria

The evolution is considered production-ready only when:

1. deterministic unit and contract tests are green;
2. cluster identities remain stable across repeated runs;
3. same-source repetition does not inflate independence;
4. weak signals can be retained without publication;
5. supporting and counter evidence remain separate;
6. cluster state is reproducible from persisted signal history;
7. merge/split operations are auditable;
8. no production frozen invariant regresses;
9. observability can explain why a signal joined or rejected a cluster;
10. a multi-run evidence window demonstrates stable behavior.

## 12. Methodological basis

The design follows established horizon-scanning principles: continuous collection of weak signals, broad source diversity, clustering of recurring topics, and subsequent development of emerging trends. Government Office for Science guidance explicitly describes horizon scanning as systematic collection of weak signals and emerging trends, and its 2025 Defra case study describes ongoing clustering/tagging of scans into emerging trends. OECD's 2025 Science, Technology and Innovation Outlook similarly emphasizes continuous horizon scanning, structured analysis, diverse sources and expert consultation under uncertainty.
