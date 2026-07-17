---
name: graph-export-visualization
description: Use this skill when producing any graph export or visualization (GraphML/GEXF/SVG/PNG, or a filtered subgraph) -- Agent 6/8 outputs, and the Phase 5 frontend export/filter logic.
---

# Skill: Graph Export & Visualization Conventions

## When to use this skill
Agent 6 (Graph Builder) when writing any filtered/exported view of the graph. Agent 8
(Topology Analysis) when producing ranked-architecture visual output. The Phase 5 frontend,
directly, when constructing a Cytoscape.js view with a client-side filter.

## The rule this skill exists to enforce

**A filter level must always be an explicit, labeled parameter in the output's filename
and/or metadata -- never implicit.** This is not a stylistic preference; it's a direct fix
for a real historical failure:

`reports/session_004_diff.md` records: "Prior `full_graph/` (63 nodes) confirmed mislabeled
subset only." A directory named as if it contained the complete graph actually contained a
`pmid_count>=2`-filtered subset (63 of 949 nodes) -- and nothing in the filename or the file
itself declared that filter. Anyone consuming `full_graph/` without reading a separate
session diff would believe it was the entire graph.

## The pmid>=2 noise filter (standard default filter level)

The canonical "reduce noise" filter used across this project is **`pmid_count >= 2`**: keep
only edges/nodes supported by at least 2 independent PMIDs, dropping single-source
(possibly idiosyncratic or overinterpreted) claims. This is a legitimate, useful default
view -- but it is a *filtered subset*, never a replacement name for "the full graph." Always
apply the naming/metadata convention below so the filter level travels with the export.

## Naming and metadata convention

- Every export directory/file name must encode its filter level, e.g.
  `graph_pmid_min2/`, `graph_unfiltered/`, `graph_loop_members_only/` -- never a bare
  `full_graph` or `master_graph` name unless it is genuinely the complete, unfiltered graph
  (verify node/edge counts match the source `knowledge_graph.json` exactly before using an
  unqualified name).
- Every export's metadata (a sidecar `.json` or embedded graph attribute) must state the
  exact filter predicate applied, e.g. `{"filter": "pmid_count >= 2", "source_node_count": 838, "exported_node_count": 122}`.

## Visual encoding conventions (for consistency across all exports/views)

- **Node color by type**: cell / cytokine / tissue / molecule / clinical_phenotype /
  pathway -- one fixed color per type, documented in the export's legend/metadata.
- **Edge thickness by PMID-support count** -- more supporting PMIDs, thicker edge.
- **Edge style by confidence** -- solid for high confidence, dashed for low/weak (single-PMID
  or evidence-level-penalized) edges.
- **Contradictory edge pairs** (from the `contradiction-detection` skill's output) rendered
  in a visually distinct color (e.g. red), with click-to-expand showing both PMIDs and any
  reconciling hypothesis.

## Formats
`.graphml`, `.gexf`, `.svg`, `.png` for static exports; the live frontend view uses
Cytoscape.js directly against the JSON graph (no export step needed for the interactive
view, only for the demo-script static artifacts).

## Success criteria
- Every filtered export's node/edge count is reproducible by applying its stated filter
  predicate to the source `knowledge_graph.json`.
- No export uses an unqualified "full"/"master" name unless independently verified to
  contain 100% of the source graph's nodes and edges.
- The same node-type -> color mapping is used consistently across every export and the live
  frontend view.
