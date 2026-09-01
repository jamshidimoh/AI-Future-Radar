# P3 Scoring Architecture

Editorial scoring measures publication suitability. Technology signal scoring measures the strength and direction of a technology signal. The two layers must not score the same concept under different names.

Editorial score dimensions: mission fit, source authority, evidence confidence, publication value, freshness.

Technology signal score uses novelty, future impact, technical significance, strategic relevance, and trend alignment. Freshness, source quality, and leader influence remain diagnostic metadata rather than duplicated final-score dimensions.

The canonical final rank is computed once from the canonical editorial score and canonical technology signal score. Story representative selection remains independent of signal inflation.

Weights are versioned policy candidates and require deterministic regression plus offline evaluation against the P1 baseline before being accepted as final policy.
