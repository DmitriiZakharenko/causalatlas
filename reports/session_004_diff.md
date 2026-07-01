# Session 004 — Graph Hardening (no hypotheses)

## Agent 4 — Full corpus mechanistic extraction
| Metric | Value |
|--------|-------|
| Full merged corpus | 1,870 papers |
| Papers with ≥1 edge | **1,403/1,870** (75.0%) |
| Session 001 baseline | 337/448 |
| S002 new papers in merge (not in S001) | 1,442 |
| S002 new papers with edges | **1,077/1,442** (74.7%) |
| S001 papers re-extracted with edges | 326/448 |
| Raw edges extracted | 5,221 |

## Graph merge + noise audit
| Stage | Nodes | Edges |
|-------|-------|-------|
| Pre-S004 (Session 002 graph) | 949 | 753 |
| Post full re-extraction (pre-noise) | 4,105 | 3,456 |
| Post noise audit (final hardened) | **838** | **1,143** |
| Net delta vs S002 | −111 nodes | **+390 edges** |

Noise removed: **3,267 nodes**, **2,313 edges** (pattern-extraction artifacts + stopword nodes).

## Agent 8 — Full contradiction scan
- Pairs with ≥2 edges: 80
- Contradictions logged: **70** → `graph/contradictions.json`
- Batf3 curated entry preserved

## Architecture re-verification (Agent 7)
- Epithelial alarmin → ILC2 → Type 2 cytokine loop: ✓ (198 PMIDs)
- Mast cell-IgE effector loop: ✓ (138 PMIDs)
- IL-5 eosinophil amplification: ✓ (332 PMIDs)
- IL-4/IL-13 Th2 positive feedback: ✓ (69 PMIDs)
- IL-13 remodeling axis: ✓ (54 PMIDs)
- Bone marrow eosinophilopoiesis axis: ✓ (43 PMIDs)
- TSLP-dendritic-Th2 axis: ✓ (69 PMIDs)
- Tissue-resident memory chronicity loop: ✓ (20 PMIDs)
- Biologic anti-TSLP: ✓ (83 PMIDs)
- Biologic anti-IL-4R: ⚠ 50% (32 PMIDs) — missing: Type 2 inflammation → Airway inflammation

## Visualization fix
- `graph/visualizations/true_full_graph/` — **838 nodes / 1045 edges** (true full export)
- `graph/visualizations/evidence_filtered_graph/` — 122 nodes / 92 edges (pmid_count≥2)
- Prior `full_graph/` (63 nodes) confirmed mislabeled subset only

## Deliverables
- `graph/graph_quality_report.json`
- `graph/contradictions.json`
- `graph/noise_audit.json`
- `graph/loops.json`, `graph/network_metrics.json` (baselines)
- Hypothesis generation deferred to Session 005
