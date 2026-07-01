# Graph data lineage

These files are **copies** of pre-existing pipeline outputs, migrated into the new
`/data/graphs/<disease>/` layout for the LoopFinder app. The originals under
`/graph/` and `/reports/` at the repo root are left untouched (per project rule: never
regenerate or overwrite pre-existing session data).

## Known discrepancy: `asthma/knowledge_graph.json`

- Session 003 (`reports/session_003_diff.md`) reports the graph as **949 nodes / 753 edges**
  and states it was unchanged from Session 002.
- A later, previously-undocumented **Session 004 ("Graph Hardening")** run
  (`reports/session_004_diff.md`) re-extracted the full corpus and overwrote
  `graph/asthma_knowledge_graph.json` **in place** with a noise-filtered version:
  **838 nodes / 1143 edges**. No pre-Session-004 backup of the raw JSON exists anywhere
  in the repo or in git history (this repo was not under git before this project), so the
  exact 949/753 node/edge set cannot be losslessly reconstructed — only its aggregate counts
  are known, from markdown reports.
- Decision (confirmed with user): Session 004 is **excluded from the Phase 4 eval flywheel
  scope** — the flywheel's historical trace data is Sessions 001–003 only, matching the
  build prompt. This has no actual effect on eval correctness because Session 004 generated
  **zero hypotheses** (explicitly deferred to a never-run "Session 005" per its own diff doc)
  — there is nothing for the judge to backfill-score from it either way.
- `asthma/knowledge_graph.json` here is copied from the **current on-disk file** (838/1143,
  post-Session-004). Fabricating a rolled-back 949/753 file by guessing which ~111 nodes /
  390 edges to remove would itself violate the "never invent data" rule, so we do not attempt
  it. This is a graph-visualization-layer (Phase 5) concern only, not an eval-flywheel
  (Phase 4) one — see `/data/sessions/asthma_004_hardening/` for the excluded artifacts.

## Layout

- `asthma/knowledge_graph.json`, `contradictions.json`, `novelty_audit.json`, `loops.json`,
  `network_metrics.json`, `modules.json`, `knowledge_gaps.json`, `graph_quality_report.json`
  — copied verbatim from `/graph/*.json` (asthma-scoped).
- `ibd/knowledge_graph.json` — copied verbatim from `/graph/ibd_knowledge_graph.json`.
- `cross_disease_motifs.json` — shared across diseases, copied verbatim from `/graph/`.
