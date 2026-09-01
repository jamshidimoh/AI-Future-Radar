# P3 Scoring Architecture

Editorial scoring measures publication suitability. Technology signal scoring measures the strength and direction of a technology signal. The two layers must not score the same concept under different names.

Editorial score dimensions:
- mission fit
- source authority
- evidence confidence
- publication value
- freshness

Technology signal score dimensions remain in signal_engine but the final signal score will use only novelty, future impact, technical significance, strategic relevance, and trend alignment. Freshness, source quality, and leader influence are editorial/policy concerns and remain diagnostic in the raw signal vector.

The canonical final rank is computed once from the canonical editorial score and canonical technology signal score. Story representative selection remains independent of signal inflation.

Weights in this document are a versioned policy candidate. Acceptance requires deterministic tests and comparison against the P1 baseline; it is not a claim of human-optimal ranking.
