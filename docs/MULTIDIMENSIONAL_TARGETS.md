# Multidimensional Target Extension

## Scope

This document is the implementation checklist for extending CausalAtlas beyond
the baseline disease-target workflow.

## Workstreams

| Workstream | Ownership | Required outcome |
| --- | --- | --- |
| Target contract | Backend/API | Versioned, validated target model with legacy normalization |
| Run persistence | Backend/DB | Additive migration and immutable target artifact per run |
| Search | Retrieval/verification | Mode-aware queries with recorded coverage and quality gates |
| Evidence quality | Verification/filtering | Explicit relevance, study type, species, context, and noise handling |
| Graph | Extraction/merge | Context-aware nodes/edges with preserved provenance and contradictions |
| UI | Frontend | Optional dimensions, clear mode display, and graph filters |
| Verification | QA | Legacy regression, schema tests, frontend checks, and reproducibility checklist |

## Drug knowledge layer

Drug input is persisted separately from drug claims. A name alone creates an
unresolved input record; it does not assert a target, indication, binding event, or
clinical efficacy. A provider adapter may add an identifier only when the provider
returned that identifier and its provenance is stored with the record.

The following predicates remain separate: `binds_target`,
`associated_with_disease`, `efficacy`, and `toxicity`. Claims without provenance
are discarded from the normalized claim set. The current provider-neutral layer
performs no network lookup; verified adapters can be added later without changing
the session contract.

## Structured context

Evidence context is represented explicitly as tissue, cell type, species,
anatomical compartment, model, and assay. Missing values use an explicit `unknown`
state. Supplied but not verified values use `unresolved`; they must not be silently
promoted to ontology-backed identifiers.

New sessions write `drug_knowledge.json` and `target_context.json` alongside the
resolved target artifact.

## Target contract

The implementation keeps `disease` required because the current pipeline and
cumulative graph namespace are disease-scoped. `genes`, `drugs`, `tissues`, and
`cell_types` are optional. Empty dimensions must not be represented as fabricated
biological facts. The resolved target, normalized identifiers, query mode, and
schema version must be stored with the run.

## Search and quality controls

Each retrieval strategy must record its exact query and source. The pipeline must
keep retrieval, verification, quality scoring, and extraction separate. A paper
can be real but irrelevant, relevant but weak, or useful for one edge and not
another. These distinctions must remain explicit.

Drug-target binding, disease association, tissue expression, cell-type activity,
and therapeutic efficacy are separate evidence claims. Canonical database records
must not acquire PMID provenance, and PMID-derived claims must not be relabeled as
canonical consensus.

Target normalization is deterministic and non-speculative. Known aliases may map to
a canonical label; unknown values remain preserved as `unresolved` raw input until a
verified provider adapter supplies an identifier. PMID presence is not relevance:
the deterministic fallback records matched target terms and rejects papers with no
target-term evidence from title, abstract, or journal metadata. Full Agent 3
verification remains the stronger gate for live agent runs.

## Noise controls

Noise heuristics may flag or hide likely extraction artifacts in the UI, but they
must not mutate or delete the underlying evidence graph. Any stage-level exclusion
must record its reason and preserve the source artifact. Filters must be explicit,
deterministic, and test-covered.

Graph exports use `MultiDiGraph` so parallel claims remain addressable by stable
claim IDs. Every export includes its source graph, filter predicate, source counts,
exported counts, and node color mapping. A filtered view is never named or described
as the complete graph.

The graph UI exposes entity-type and provenance filters. These are display-only
filters: the underlying graph artifact and its evidence are not modified.

## Compatibility gate

The extension is ready only when the following remain true:

- the `v0.2.0` tag resolves to the original baseline;
- legacy disease/gene requests pass unchanged;
- historical sessions and graphs load;
- offline replay still works;
- canonical and PMID provenance remain separate;
- failed and partial runs remain inspectable;
- backend tests, frontend lint/typecheck/build, API health, and read-only replay
  pass.
