# Asthma Mechanistic Knowledge Graph — Session 002

**Disease:** Asthma  
**Publication window:** 2021–2026  
**Graph version:** 2.0.0  
**Primary artifact:** `graph/knowledge_graph.json` (alias: `graph/asthma_knowledge_graph.json`)

---

## Executive Summary

Session 002 corrected Session 001's temporal corpus bias, re-audited H1/H2 with logged external PubMed searches, logged the Batf3/cDC1 chronic HDM contradiction without resolution, and extended the cumulative graph from **947→949 nodes** and **742→753 edges** without overwriting provenance.

**No hypotheses were accepted.** Session 001 H1/H2 were reclassified and removed from the hypothesis pipeline. All three priority gaps were closed or downgraded to established mechanisms upon external search.

---

## 0. Mandatory Re-Audit (Before New Generation)

### Agent 9 — Novelty Verification (`graph/novelty_audit.json`)

| ID | Original claim | Step 1 | External search | Reclassification | Action |
|---|---|---|---|---|---|
| **H1** | Batf3/cDC1 required for lung TRM sustaining chronic asthma | RESTATED (PMID 40184040 conclusion) | 3 queries; cDC1+TRM+lung allergic → only PMID 40184040 | **RESTATED / B** | Folded as established edge; not carried forward |
| **H2** | IL-33/ILC2/IL-5 couples airway to marrow eosinophilopoiesis | Recombination of known parts | IL-5 eosinophilopoiesis: 71 hits; reviews PMID 29731004 (2018), 33669458 (2021) | **A — Established consensus** | Folded into graph; not carried forward |

### Agent 8 — Batf3/cDC1 Contradiction (`graph/contradictions.json`)

| Edge | PMID | Year | Model | Mechanism | Direction |
|---|---|---|---|---|---|
| A | 40184040 | 2025 | Long-term HDM | TRM / Cxcr6+ CD4+ TRM absent in Batf3⁻/⁻ | Batf3 loss → **reduced** chronic inflammation |
| B | 28515363 | 2017 | Chronic HDM | CD103+ cDC1 IL-12 restrains Th2/Th17 | Batf3 loss → **exacerbated** chronic inflammation |

**Status:** UNRESOLVED. Both edges retained. Pre-2021 PMID 28515363 added to corpus explicitly for this contradiction. Context: PMID 41025995 (ozone model) shows Batf3⁻/⁻ lower AHR — different trigger, same reduced-inflammation direction.

---

## 1. Retrieved Papers (Agent 1) — Year-Band Stratification

| Year band | PMIDs retrieved (search) | Papers in merged accepted corpus |
|---|---|---|
| 2021–2022 | 644 | **435** |
| 2023–2024 | 656 | **595** |
| 2025–2026 | 676 | **839** |
| Pre-2021 / unknown | — | 1 (PMID 28515363) |

| Corpus metric | Count |
|---|---|
| Session 001 preserved | 448 |
| New PMIDs retrieved | 1,576 |
| Merged accepted (Agent 2) | **1,870** |
| Rejected (relevance <0.35) | 152 (7.5%) |

Gap-targeted queries additionally retrieved papers for TSLP→T2, Eosinophil→inflammation, DC→TRM, and Batf3.

Full quality report: `graph/graph_quality_report.json`

---

## 2. Verification Report (Agent 2)

- **Rejection rate:** 7.5% (152/2,022 deduplicated candidates) — no longer 0%
- Each paper scored 0–1 on mechanistic asthma relevance
- Papers without asthma/mechanism keyword overlap rejected

---

## 3. Evidence Summary (Agent 3)

Expanded corpus now spans all three year bands proportionally (435 / 595 / 839), correcting Session 001's 96%–2026 bias.

Top supported core edges after merge (representative):

| Edge | PMID count (graph) |
|---|---|
| Eosinophil → Airway inflammation | 251 |
| TSLP → Type 2 inflammation | 54 |
| Type 2 inflammation → Eosinophil | 66+ |
| IL-5 → Eosinophil | 29+ |
| Batf3 → Airway inflammation | 2 (opposite directions) |

---

## 4. Mechanistic Extraction (Agent 4)

- **1,427 new edges** extracted from papers not in Session 001 (+ PMID 28515363)
- Each edge includes `evidence_sentence` where template-matched
- Session 001 edge PMID lists preserved and appended, not replaced

---

## 5. Unified Knowledge Graph (Agent 5)

| Metric | Session 001 | Session 002 |
|---|---|---|
| Nodes | 947 | **949** |
| Edges | 742 | **753** |
| Version | 1.0.0 | **2.0.0** |

Files: `graph/knowledge_graph.json`, `graph/asthma_knowledge_graph.json`

---

## 6. Loop Discovery (Agent 6) — `graph/loops.json`

| Loop | Completeness | PMIDs |
|---|---|---|
| Epithelial → IL-33 → ILC2 → IL-5 → Eosinophil | 100% | 190 |
| Mast cell–IgE effector | 100% | 128 |
| **TSLP → Type 2 inflammation** (newly complete) | 100% | 76 |
| Th2 positive feedback | 100% | 45 |
| IL-5 → Bone marrow → Eosinophil | 100% | 42 |
| Batf3–TRM chronicity | 100% | 19 |

---

## 7. Topology Analysis (Agent 7) — `graph/network_metrics.json`

Core subgraph degree leaders include Type 2 inflammation, Eosinophil, Airway inflammation, IL-5, Th2 cell, TSLP.

---

## 8. Contradictions & Gaps (Agent 8)

### Contradictions (`graph/contradictions.json`)
- **BATF3-CHRONIC-HDM-001** logged (see Section 0)

### Priority gaps — Session 002 resolution

| Gap | Session 001 | Session 002 | Agent 9 external class |
|---|---|---|---|
| TSLP → Type 2 inflammation | Missing | **EVIDENCED** (54 PMIDs) | B — Previously published (124 hits) |
| Eosinophil → Airway inflammation | Missing in loop | **EVIDENCED** (251 PMIDs) | A — Established consensus (818 hits) |
| DC → TRM priming (asthma) | Untested | **INSUFFICIENT EVIDENCE** for asthma-specific cDC1→TRM | Asthma/cDC1 query → only PMID 40184040; general DC priming hits (e.g. PMID 33952647) are influenza vaccine TRM, not allergic asthma |

---

## 9. Novelty Verification — Session 002 Candidates (`graph/novelty_audit.json`)

No gap candidate reached **D or E** classification. All three priority targets classified A or B → **ineligible for Agent 10**.

---

## 10. Hypothesis Generation (Agent 10)

**No hypotheses generated.** v2 gate enforced: only D/E classifications proceed.

---

## 11. Peer Review (Agent 11)

No hypotheses reached review. Session 001 H1/H2 retroactively would have failed Agent 9 gate.

---

## 12. Experiment Design (Agent 12)

**No experiments designed** — no accepted hypotheses.

**Recommended follow-up (not hypotheses):** Directly compare HDM protocols between PMID 28515363 and 40184040 to test whether Batf3 contradiction is protocol-dependent — this would be a **C-class contradiction-resolution** study, not a D/E novelty hypothesis.

---

## Session 002 Follow-Up (completed)

### Visualization Pipeline — `graph/visualizations/`

Seven views exported in `.graphml`, `.gexf`, `.svg`, `.png`. Manifest: `graph/visualizations/visualization_manifest.json`.

### C-Class Hypothesis H-C001 — ACCEPTED

See `reports/session_002_hypothesis_HC001.json`, `novelty_audit.json` → `c_class_hypotheses`, and Agent 12 design in `reports/session_002_hypothesis_HC001_experiments.json`.

---

## Mandatory Outputs Checklist

| File | Status |
|---|---|
| `graph/graph_quality_report.json` | ✓ |
| `graph/knowledge_graph.json` | ✓ |
| `graph/loops.json` | ✓ |
| `graph/network_metrics.json` | ✓ |
| `graph/modules.json` | ✓ |
| `graph/contradictions.json` | ✓ |
| `graph/knowledge_gaps.json` | ✓ |
| `graph/novelty_audit.json` | ✓ |
| `graph/top_loops.md` | ✓ |
| `graph/network_summary.md` | ✓ |
| `reports/session_002_diff.md` | ✓ |

---

*All PMIDs traceable to PubMed. No papers, mechanisms, or results invented.*
