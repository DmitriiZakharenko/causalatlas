# Session 002 Diff vs Session 001

## Corpus
- Session 001: 448 papers (430/448 from 2026 — temporal bias)
- Session 002 merged: 1870 papers after year-band stratification
- New PMIDs added: 1576
- Year-band distribution: 2021-22=435, 2023-24=595, 2025-26=839, other=1
- Pre-2021 PMID 28515363 added for Batf3 contradiction evidence

## Hypothesis reclassification
- H1 (cDC1/TRM chronicity): **RESTATED** → folded as established edge under PMID 40184040
- H2 (IL-33/ILC2/marrow): **A/Established consensus** → folded into eosinophilopoiesis literature, not carried forward

## New contradictions logged
- Batf3 knockout chronic HDM: PMID 40184040 (reduced inflammation, TRM) vs PMID 28515363 (exacerbated inflammation, IL-12) — **UNRESOLVED**

## Graph changes
- Nodes: 947 → 949
- Edges: 742 → 753
- Priority gaps after session:
  - TSLP → Type 2 inflammation: EVIDENCED (54 PMIDs)
  - Eosinophil → Airway inflammation: EVIDENCED
  - DC → TRM: EVIDENCED

## Novel D/E hypotheses generated
- **None reached Agent 10.** All three Session 002 priority gaps classified A or B by Agent 9 external search (see above).

## C-Class hypothesis (follow-up)
- **H-C001** (Batf3/cDC1 contradiction resolution): **ACCEPTED** at Agent 11 (2 ACCEPT, 1 UNCERTAIN)
- Agent 9: **C — Conflicting literature** (5 PubMed queries, 0 hits for pre-stated resolving variable)
- Agent 12: `reports/session_002_hypothesis_HC001_experiments.json`

## Visualizations (follow-up)
- 7 views × 4 formats under `graph/visualizations/` — see manifest

## Priority gap resolution
| Gap | Session 001 | Session 002 | Notes |
|---|---|---|---|
| TSLP → Type 2 inflammation | Missing | **EVIDENCED** (54 PMIDs in graph) | Closed via expanded 2021–2024 corpus |
| Eosinophil → Airway inflammation | Missing in loop | **EVIDENCED** (251 PMIDs) | Established consensus (Agent 9: A) |
| DC → TRM priming | Untested | **EVIDENCED** but thin | Graph edge PMID 33952647 (general lung); asthma/cDC1-specific still single-source (40184040 only) |
