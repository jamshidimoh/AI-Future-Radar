# Language Gate Policy

The Persian language gate applies a stricter threshold to `summary` and `why_it_matters` than to `title`.

Titles may contain official Latin-script names of products, companies, models, and projects. A lower title threshold prevents valid Persian news from being rejected merely because an official name occupies part of the title.

The summary and why-it-matters fields remain subject to the normal Persian-language threshold, so this change does not bypass the editorial language contract.

## Recovery contract

When a provider returns a draft whose `title`, `summary`, or `why_it_matters` fails the language contract, the pipeline first attempts one bounded **full-draft Persian recovery** using the existing quality-provider chain. The recovery rewrites all three editorial fields from the original source evidence and is accepted only if the normal language and length gates pass.

Title-only recovery remains a secondary fallback for cases where the summary is already valid Persian but the title alone is not. It is not sufficient for an otherwise English draft.

No threshold is lowered and no recovery output bypasses the final language or length gates. If recovery fails, the candidate is rejected rather than published in a non-Persian form.
