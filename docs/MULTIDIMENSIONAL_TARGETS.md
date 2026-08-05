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

## Noise controls

Noise heuristics may flag or hide likely extraction artifacts in the UI, but they
must not mutate or delete the underlying evidence graph. Any stage-level exclusion
must record its reason and preserve the source artifact. Filters must be explicit,
deterministic, and test-covered.

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
