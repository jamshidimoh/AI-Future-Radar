# G3 — Evidence Graph and Claim Provenance

Status: IMPLEMENTED — VALIDATION EVIDENCE RECORDED; FINAL REVISION VALIDATION REQUIRED

G3 adds a deterministic, serializable evidence graph for technology intelligence. It is intentionally publication-decoupled.

## Scope

The graph represents three node types:

- `source`: a canonical source URL/title and source type.
- `claim`: a normalized claim identity.
- `trend`: a trend identity, normally supplied by the G2 registry.

Supported relations are:

- `supports`: a source provides supporting evidence for a claim.
- `contradicts`: a source provides contradictory evidence for a claim.
- `derived_from`: a trend is derived from one or more claims.
- `observed_in`: reserved for future temporal/source observation edges.

Every edge has a confidence value in `[0, 1]`. Unknown nodes, invalid relations, invalid confidence, duplicate node identities, and incompatible relation endpoints fail closed.

## Determinism

Source identity is derived from a canonical URL when available, removing common tracking parameters and normalizing scheme/host/path. Claim identities are derived from normalized claim text. Trend identities use an explicit registry identity when supplied or a deterministic member-set identity otherwise.

Graph nodes and edges are emitted in deterministic order. Equivalent input order therefore produces the same graph representation.

## Provenance model

A claim is never treated as self-authenticating. Its provenance is represented by explicit `source -> claim` evidence edges. Contradictory evidence is retained rather than overwritten, enabling later stages to reason about disagreement and uncertainty.

A G2 trend may point to its supporting claims with `claim -> trend` `derived_from` edges. G3 does not infer publication eligibility from these relationships.

## Persistence and integration policy

G3 does not modify Telegram delivery, publication ranking, editorial eligibility, quota, or the current production publication path. `config/evidence_graph.yaml` is disabled by default. The layer can therefore be validated independently before controlled integration in later gates.

## Initial validation evidence

Workflow run `33599132196`, job `100148721905`, validated immutable G3 head `f7ef53a1bf061aa1b5c97a009941cdc5f26fe338`:

- full repository regression: 497 passed;
- G3 focused contract: 13 passed;
- frozen/final production acceptance tests: 12 passed;
- publication-decoupling contract: PASS.

Because this documentation update changes the branch SHA, the evidence above is historical and the new immutable head must be revalidated before G3 can be declared complete.

## Non-goals

G3 does not implement temporal acceleration/persistence, cross-domain convergence, foresight/scenario generation, or production shadow-mode measurement. Those are later gates.
