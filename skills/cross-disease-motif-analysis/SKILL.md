---
name: cross-disease-motif-analysis
description: Use this skill when comparing two or more disease knowledge graphs to identify shared vs. disease-specific fully-evidenced motifs -- generalizes the Session 003 asthma-vs-IBD comparison to N diseases.
---

# Skill: Cross-Disease Motif Analysis

## When to use this skill
Whenever more than one disease graph exists under `data/graphs/` and a comparison is
requested (Agent 7 as part of architecture ranking, or directly by the Phase 5 frontend's
cross-disease motif view). Must work for N diseases, not be hardcoded to a pair.

## Procedure

1. **Load all N disease graphs** to compare (e.g. `data/graphs/asthma/knowledge_graph.json`,
   `data/graphs/ibd/knowledge_graph.json`, plus any additional target run during Phase 2
   validation).
2. **Define a motif** as a specific node-type/edge-type path (e.g. "barrier epithelium ->
   alarmin cytokine -> innate lymphoid cell -> effector cytokine"), abstracted away from the
   exact node names so it can be checked for presence across diseases with different specific
   molecules (e.g. IL-33 in asthma vs. IL-22 in IBD can both instantiate an "alarmin/effector
   cytokine -> barrier maintenance" motif).
3. For each candidate motif, compute **per-disease evidence**: is the motif fully evidenced
   (every edge in the path has real PMID support) in each graph, partially evidenced, or
   entirely absent?
4. Classify each motif as:
   - **Shared, fully evidenced in >=2 diseases** -- a reusable immune architecture.
   - **Disease-specific, fully evidenced in exactly 1 disease, absent/untested in others** --
     worth flagging as either a genuine biological difference or an under-studied gap in the
     other disease's corpus (check corpus size/year-band before concluding it's biological).
   - **Partially evidenced everywhere** -- a candidate for a D-class hypothesis in whichever
     disease is closest to complete.
5. **Generalize the comparison table over N diseases** -- output a matrix (motif x disease),
   not a hardcoded two-column asthma/IBD table. Adding a third disease must not require
   rewriting this analysis, only adding a row to the input disease list.

## Real historical instance (Session 003, the case this skill generalizes)

`reports/session_003_diff.md`: "ILC3->IL-22->barrier fully evidenced in IBD (84 PMIDs),
absent in asthma; epithelial->ILC2->T2 fully in asthma (190 PMIDs), absent in IBD." This is a
2-disease instance of the general procedure above -- both are barrier-immune-loop motifs,
each fully evidenced in one disease and untested (not necessarily biologically absent) in the
other, given each disease's corpus was independently and asymmetrically retrieved.

## Hard constraint
Before classifying a motif "disease-specific" (biologically real difference) rather than
"under-studied" (corpus gap), check whether the disease lacking evidence for that motif has
a comparably sized/comprehensive corpus for the relevant node types. Do not conclude
biological specificity from a corpus gap.

## Success criteria
- The comparison runs unmodified when a 3rd, 4th, ... Nth disease graph is added to the input
  list.
- Every "shared" motif classification cites the PMID count supporting it in each disease
  where it's fully evidenced.
- Every "disease-specific" classification includes the corpus-comparability check, not just
  the presence/absence result.
