# Persian editorial and Telegram publication standard

## Purpose

This standard improves Persian-language accuracy, editorial clarity and Telegram presentation. The channels in `config/editorial_inspiration.yaml` are used only to study presentation patterns. They are not content feeds, evidence sources or substitutes for original reporting.

## Editorial structure

Every publication must answer three different questions:

1. **What happened?** State the event, actor and material novelty in the first sentence.
2. **What does the evidence say?** Preserve the method, model/version, benchmark, data, date, scale, availability status and stated limitations when present.
3. **Why does it matter?** Explain a concrete consequence or mechanism; do not paraphrase the summary.

The headline should be concise, factual and specific. Avoid clickbait, empty superlatives and vague announcements. A product launch, research result, security incident, executive opinion and analytical forecast need different framing.

## Persian translation and terminology

- Persian is the default language for titles, summaries and explanations, including paragraphs that begin with a Latin product or organization name.
- Rewrite for natural Persian syntax. Do not mirror English sentence order or translate word-for-word.
- Use standard Persian Yeh and Kaf, correct half-spaces (ZWNJ), Persian punctuation and consistent spacing.
- Prefer established Persian technical terms. Use the official English term in parentheses on first use only when it prevents ambiguity or is important for discoverability.
- Keep official names of people, organizations, products, models, software and research projects in their canonical Latin spelling.
- Do not replace technical distinctions with loose synonyms. Distinguish training from inference, model from agent, prototype from deployed product, and benchmark score from real-world reliability.
- Preserve numbers, units, comparison baselines, dates and uncertainty. Never invent a missing model version, metric, role, causal explanation or quotation.
- Remove translationese, administrative filler and repeated generic phrases. Prefer active verbs, concrete subjects and medium-length sentences.

## Genre-specific rules

| Genre | Required editorial treatment |
|---|---|
| Product/model release | Identify the product, creator, new capability, version and actual release/availability status. Attribute company claims. |
| Research | Preserve research question, method, data/sample, evaluation and limitations. Distinguish peer-reviewed work from preprints and technical reports. |
| Expert voice | Attribute each view to the speaker; distinguish the speaker's claim from the publisher's reporting and the Radar's analysis. |
| Security/safety | Separate confirmed incidents from allegations or scenarios; report scope, affected systems and mitigations only when sourced. |
| Analysis/forecast | Separate evidence from interpretation and make assumptions, time horizons and uncertainty visible. |
| General news | Lead with the event; avoid long introductions and repeated context. |

## Telegram layout and right-to-left behavior

- Every non-empty display line must have an explicit RTL base direction, even when it starts with `OpenAI`, `DeepMind`, a model name, a Latin acronym or a URL.
- Isolate Latin runs inside Persian text; never reverse or rewrite official identifiers to force visual alignment.
- Apply bidirectional controls only at the presentation layer. Do not allow model-generated or source-provided control characters into editorial fields.
- Use a compact content-type label (news, product release, research, analysis, expert voice or security) when it improves scanning.
- Show speaker attribution when relevant and when the name is not already clear in the headline or summary.
- Keep the main message atomic and readable. Do not add decorative metadata unless it helps the reader.

## Source and evidence hierarchy

1. Original research paper, journal, technical report, transcript, dataset or official product documentation.
2. First-party research-lab, university, standards-body or company announcement (claims remain attributed).
3. Established specialist and general technology journalism with a traceable original source.
4. Expert newsletters and independent analysis for context and discovery; distinguish opinion from fact.
5. Social posts and Telegram channels only as low-authority discovery signals or style references, never as the sole evidence for factual claims.

Discovery sources must not inherit the authority of the publisher they mention. Prefer the original source for publication whenever it can be recovered. Keep the existing global arXiv exclusion and do not add Telegram channels to the RSS registry.

## Preserved Radar constraints

This style standard does not change the Radar's mission or selection policy: AI remains central; cross-domain coverage needs a material AI connection; expert interviews and statements, major product/model announcements, mind/consciousness and cognitive science, philosophy of science, future studies, quantum, BCI, robotics and AI-biology remain eligible under their existing gates. Existing quality floors, source diversity, freshness, deduplication, leader coverage, medical/genetics safeguards and adaptive publication ceiling remain in force. The operational ceiling is not a fixed publication quota.

## Validation

Automated tests cover Persian Unicode normalization, half-space repairs, source authority, genre-specific prompt guidance, speaker attribution and RTL wrapping of every non-empty Telegram line. CI remains the final acceptance authority.
