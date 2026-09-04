# MSA V1 Benchmark Matrix

Status: **READY FOR EXECUTION**

The benchmark compares the frozen Current Radar baseline with MSA V1 on the same input corpus and configuration. It is a validation artifact, not a production change.

## Required test families

| ID | Test | Expected behavior | Primary metric |
|---|---|---|---|
| B01 | Single authoritative source | retain high-value candidate despite low source count | recall |
| B02 | Repost cascade | collapse copies into one evidence cluster | convergence precision |
| B03 | Weak signal | retain with low confidence rather than delete | weak-signal recall |
| B04 | Hype storm | popularity does not create confidence | false-positive rate |
| B05 | Old story/new evidence | update existing story | temporal consistency |
| B06 | Old story/new title | detect duplicate | duplicate precision |
| B07 | Conflicting evidence | expose uncertainty/contradiction | evidence integrity |
| B08 | Multi-provider outage | detect infrastructure/systemic candidate without claiming common cause | systemic-risk precision |
| B09 | High importance/low confidence | watch/verify rather than publish as fact | calibration |
| B10 | Low importance/high confidence | deprioritize | ranking precision |
| B11 | Taxonomy miss | register TAXONOMY_GAP | blind-spot recall |
| B12 | Source miss | register SOURCE_GAP | blind-spot recall |
| B13 | Cross-domain convergence | connect AI + quantum/BCI/bio/robotics when evidence supports it | convergence recall |
| B14 | Source drift | reduce future source quality without rewriting history | temporal source consistency |
| B15 | Provider failure | fail closed | safety |
| B16 | Malformed LLM output | reject/recover without fabrication | robustness |
| B17 | Determinism | same input/config produces stable ranking | reproducibility |
| B18 | Explainability | every top decision has traceable factors | traceability |
| B19 | Novel research breakthrough | preserve technical evidence and limitations | evidence recall |
| B20 | Future-of-work/cognition signal | recognize relevant non-breaking signals | mission recall |

## Gate rules

PASS requires all safety invariants and no critical regression against the baseline.

A candidate improvement is valid only when it improves recall/precision/signal quality or blind-spot detection without weakening evidence integrity, duplicate control, fail-closed behavior, or traceability.

A higher aggregate score alone is insufficient. Critical failures override aggregate ranking.

## Required output

For each run record:

- corpus identifier
- baseline version
- MSA version
- configuration hash
- candidate count
- selected count
- published count
- duplicates
- evidence clusters
- independent convergence
- signal labels
- importance
- confidence
- priority
- editorial decision
- blind-spot classification
- failures/rejections
- traceability status

Final decision values:

`MSA_ACCEPT`
`MSA_ACCEPT_WITH_LIMITATIONS`
`MSA_REVISE`
`MSA_REJECT`

Until the benchmark is executed, MSA V1 remains a validated design specification, not a proven superior production algorithm.
