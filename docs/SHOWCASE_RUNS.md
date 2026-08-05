# Showcase Runs

This file defines reproducible live-run inputs for demonstrations. A showcase run
is an evidence-graph exercise, not a clinical recommendation and not proof that a
drug is effective.

The latest wide-run assessment is documented in
[Showcase Quality Audit](SHOWCASE_QUALITY_AUDIT.md). Read it before treating a
showcase graph as a research input.

## Wide multidimensional showcase

Use this first when validating the full target contract:

```json
{
  "disease": "asthma",
  "gene": "IL33",
  "target": {
    "schema_version": "target.v1",
    "disease": "asthma",
    "genes": ["IL33"],
    "drugs": ["itepekimab"],
    "tissues": ["lung"],
    "cell_types": ["airway epithelial cell"],
    "query_mode": "multidimensional"
  },
  "autonomy_level": "let_it_rip"
}
```

This run exercises:

- disease–gene literature retrieval;
- drug–target and drug–disease query strategies;
- lung and airway epithelial context queries;
- `analysis_target.json`;
- `drug_knowledge.json`;
- `target_context.json`;
- context-aware graph claims and provenance filters.

The name `itepekimab` is an input term only. Until a verified provider or
publication supplies a claim with provenance, the drug remains `unresolved` and
the pipeline must not infer an identifier, target, indication, or efficacy.

## Suggested follow-up showcases

Run these separately so their graphs remain independently inspectable:

| Example | Disease | Gene | Drug | Tissue | Cell type |
| --- | --- | --- | --- | --- | --- |
| Airway alarmin | asthma | IL33 | itepekimab | lung | airway epithelial cell |
| Intestinal barrier | IBD | NOD2 | — | intestine | intestinal epithelial cell |
| Fibrotic signaling | idiopathic pulmonary fibrosis | IL11 | — | lung | lung fibroblast |

Use a new run for each example. Do not overwrite historical graph artifacts.

## Verification expectations

For each showcase, inspect:

1. the resolved target and normalized/unresolved states;
2. query strategies, total hit counts, pagination, and year-band distribution;
3. rejected papers and their reasons;
4. graph edge provenance, context, sessions, and contradiction records;
5. whether any drug claim is actually backed by a canonical source or PMID.
