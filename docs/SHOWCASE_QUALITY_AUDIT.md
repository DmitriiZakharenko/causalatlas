# Showcase Quality Audit

This audit records what the wide showcase run actually established. It is a
software and evidence-quality report, not a clinical or therapeutic conclusion.

Run: `asthma_20260805T092338Z`  
Target: asthma + IL33 + itepekimab + lung + airway epithelial cell  
Completed: 2026-08-05

## Executive assessment

The run completed technically, but the scientific output is **degraded and not
ready for hypothesis-driven use**. The graph is useful as an exploratory
visualization of retrieved claims, not as a clean, validated disease–gene–drug–
tissue mechanism.

## Observed evidence

| Check | Observed result | Interpretation |
| --- | --- | --- |
| Retrieval | 6 query strategies; 100 unique retrieved publications | Broad enough for a showcase, but the query budget omitted explicit tissue and cell-type strategies in this run. |
| Verification | 76 retained and 24 rejected in `verification_report.json` | Rejection reasons are preserved, including relevance failures and one metadata mismatch. |
| Persisted corpus | 94 records in `publications_verified.json` | This conflicts with the verification report and is itself a quality defect; the UI now flags this discrepancy instead of hiding it. |
| Graph | 93 evidence nodes and 82 edges; 2 loops; 0 contradictions | Structure exists, but graph size does not imply biological validity. |
| Canonical baseline | 0 entries; fallback artifact | No canonical database facts were materialized for this run. |
| Drug layer | itepekimab is `unresolved`; 0 claims and 0 identifiers | The run correctly did not infer a drug identifier, target, indication or efficacy. |
| Tissue/cell normalization | lung and airway epithelial cell are `unresolved` | Context was captured as input, not verified biological mapping. |
| Downstream stages | 4 fallback artifacts; readiness `false` | The run must not be presented as a successful novelty-to-experiment result. |

The persisted graph also contains claims that are not obviously specific to the
requested target, including unrelated disease/context terms. These must remain
inspectable but should be filtered or rejected before a production-quality
mechanism graph is used for interpretation.

## Required improvements

The current implementation now adds a deterministic normalization record for every
input dimension (`raw`, normalized label, canonical comparison key, status, and
method), a `strict-v2` claim gate, and a local extraction fallback when model output
contains too few sentence-grounded edges. These changes intentionally reduce graph
size when the evidence is weak. The next showcase should be rerun and compared by
accepted-edge count, PMID support, target relevance, and rejected-claim reasons.

1. Make the Codex JSONL parser extract the final `agent_message` and usage event
   instead of treating the entire transcript as the model result. This is now
   implemented for new runs.
2. Make Agent 2 allocate budget explicitly across gene, drug, tissue and cell
   type strategies; a six-query cap must not silently crowd out populated
   dimensions.
3. Make Agent 3/4 write one authoritative verified-publication artifact and
   assert that its count matches the verification report before graph stages.
4. Keep canonical lookup and drug/context normalization as hard quality gates:
   unresolved input must remain unresolved and must lower readiness.
5. Add claim-level target relevance checks before graph merge. Claims that do not
   mention the disease, target, context, or a documented mechanistic bridge
   should be retained in rejected/side evidence, not merged into the main graph.
6. Require concrete novelty candidates with logged independent searches. A
   fallback label such as “mechanistic gap candidates” is not a hypothesis.
7. Require valid peer-review and experiment-design schemas before any accepted
   hypothesis is shown as ready.

## What the graph means today

Edges are published-evidence extraction records with provenance, not biological
truth. The new graph legend distinguishes input-only target dimensions from
evidence nodes, and the UI keeps weak or contradictory claims visually visible.
Use the unfiltered graph for audit and the explicitly labelled filtered views
for exploration.
