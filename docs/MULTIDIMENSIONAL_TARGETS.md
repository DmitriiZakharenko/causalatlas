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

For graph display, `binds_target` and `indirectly_modulates` claims for the same
drug and endpoint are rendered as one `drug_mechanism` edge with
`relation_variants`. This prevents duplicate arrows while preserving distinct
evidence types and all PMID/source-sentence references in the edge detail panel.
Intermediate pathway or protein edges are retained only when both endpoints occur
in the same PMID-backed source sentence; the system does not infer an unobserved
mechanism from the input pair alone.

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

For graph construction, the `strict-v2` claim gate additionally requires a PMID,
known endpoint types, an exact supporting source sentence containing both endpoints,
and demonstrated relevance to the requested target. Rejected claims are written to
`edge_quality_gate.json`; they are not silently deleted. If model extraction yields
fewer than three accepted claims, the inexpensive deterministic extractor is run as
a bounded fallback and its accepted claims are merged only after the same gate.

Search expansion is intentionally selective. The first pass covers each populated
target dimension, then at most two follow-up queries may be derived from the highest-
support, target-relevant normalized nodes. Follow-ups must add a new node/context
combination, deduplicate PMIDs, and remain within the retrieval publication and
deadline budgets. The system does not issue one query per node.

When an edge is selected in the graph UI, up to five exact supporting sentences are
shown with PMID links. These are evidence excerpts for review, not generated
interpretations or proof of biological truth.

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

Each new analysis writes an immutable run-scoped graph snapshot. It does not
inherit the disease-level latest alias, so changing the gene, drug, tissue, or
cell type produces a comparable graph rather than a cumulative copy of a
previous run. Historical snapshots remain selectable by `run_id`; the
disease-level file is only a backward-compatible latest alias.

Interpretation is restricted to auditable edges: PMID provenance, preserved source
sentence, and target relevance are required. A graph with fewer such edges is
reported as underpowered rather than filled with plausible narrative. This favors a
small, biologically meaningful subgraph over a large collection of weak fragments.

The graph stage also applies `deterministic-v1` semantic validation. For directed
claims, the supporting sentence must contain a compatible causal cue; claims that
only state co-occurrence (for example, a cell was detected in a tissue) cannot be
rendered as activation, induction, or suppression. Tissue and cell claims must also
retain biological context. This stage uses no additional LLM calls and therefore has
zero token cost.

Canonical baseline sources are shown as a separate evidence overlay. Dotted
`canonical_supports_context` links connect a canonical source hub to the nodes it
curates; these are provenance links, not causal biological edges and must remain
visually distinct from PMID evidence.

Entity aliases are normalized within biological role: for example, `itepekimab`
and `Itepekimab` merge as the same drug, while gene `IL33` and cytokine/protein
`IL-33` remain distinct typed entities. They share an alias key for lookup but
are not silently collapsed into one biological node.

## Compatibility gate

## Analysis modes

New UI/API runs default to `analysis_mode=graph_only`. This mode completes
retrieval, verification, quality scoring, mechanistic extraction, semantic graph
validation, topology, contradiction and gap analysis, then writes explicit skipped
artifacts for novelty, hypotheses, peer review, and experiment design. The prior
workflow remains available as an explicit `analysis_mode=full` request. This keeps
the expensive hypothesis stages focused on a graph fragment selected by a human.

The extension is ready only when the following remain true:

- the `v0.2.0` tag resolves to the original baseline;
- legacy disease/gene requests pass unchanged;
- historical sessions and graphs load;
- offline replay still works;
- canonical and PMID provenance remain separate;
- failed and partial runs remain inspectable;
- backend tests, frontend lint/typecheck/build, API health, and read-only replay
  pass.
