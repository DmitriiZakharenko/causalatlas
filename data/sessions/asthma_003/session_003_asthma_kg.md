# Session 003 Report

**Asthma graph unchanged** (949 nodes / 753 edges). Closed gaps not re-opened.

---

## Track 1 — H-D001 (Single-PMID / POORLY STUDIED)

**Source:** PMID [40184040](https://pubmed.ncbi.nlm.nih.gov/40184040/) — sole asthma anchor for cDC1→TRM; Cxcr6+ TRM correlation only.

**Specific prediction (NOT tested by 40184040):**
> Sorted lung **Cxcr6+ CD4+ TRM** from WT mice are **necessary and sufficient** to restore **long-term** (not short-term) HDM-induced airway inflammation and AHR when adoptively transferred into **Batf3⁻/⁻** recipients.

| What 40184040 tested | What it did NOT test |
|---|---|
| Batf3 required for cDC1 and TRM | Causal necessity of Cxcr6+ TRM |
| scRNA correlation: Cxcr6+ subset absent in Batf3⁻/⁻ | Adoptive transfer rescue |
| Short-term HDM normal; long-term attenuated | Cxcr6 blockade/deletion phenocopy |

**Agent 9:** D — Partially established. Four PubMed queries for adoptive-transfer/causal Cxcr6+ TRM prediction → **0 hits**.

**Agent 11:** ACCEPT (2 ACCEPT, 1 UNCERTAIN)

**Agent 12:** `reports/session_003_report.json` → experiments E-D001-1 (adoptive transfer), E-D001-2 (Cxcr6 blockade)

---

## Track 2 — H-C002 (Batf3 Contradiction Moderator)

**Contradiction:** PMID 28515363 (chronic HDM → **exacerbated**) vs PMID 40184040 (long-term HDM → **attenuated**)

**Specific prediction (beyond H-C001 general framing):**
> Under one harmonized chronic HDM protocol, Batf3⁻/⁻ show a **biphasic** phenotype: BAL eosinophils/AHR **exceed WT at weeks 4–6** (IL-12-restraint loss), then **fall below WT at ≥8 weeks** when TRM establishment kinetics diverge.

**Agent 9:** C — Conflicting literature. Four queries for biphasic crossover week → **0 hits**.

**Agent 11:** ACCEPT (2 ACCEPT, 1 UNCERTAIN) — conditional on TRM kinetics being slower than IL-12 loss

**Agent 12:** E-C002-1 (weekly sacrifice weeks 2–10), E-C002-2 (IL-12p40⁻/⁻ vs TRM depletion at week 6)

---

## Track 3 — Cross-Disease Motif Comparison (Asthma vs IBD)

**IBD graph:** `graph/ibd_knowledge_graph.json` — 266 PMIDs retrieved, 11 canonical nodes, 14 merged edges (303 raw extractions)

**Report:** `graph/cross_disease_motifs.json`

| Motif | Asthma | IBD | Transfer note |
|---|---|---|---|
| Epithelial alarmin → ILC2 → Type 2 | **100%**, 190 PMIDs | **0%**, 0 PMIDs | Fully evidenced in asthma; **absent in IBD** |
| TSLP → Type 2 inflammation | **100%**, 76 PMIDs | **50%**, **1 PMID** (36182776) | Multi-source asthma; **single-source IBD** |
| IL-5 → Bone marrow → Eosinophil | **100%**, 42 PMIDs | absent | Asthma-specific amplification loop |
| NOD2 → epithelial barrier | absent | **67%**, 22 PMIDs | **IBD-specific** (not in asthma graph) |
| IL-23 → Th17 → intestinal inflammation | absent | **67%**, 18 PMIDs | **IBD-specific** |
| ILC3 → IL-22 → barrier repair | absent | **100%**, 84 PMIDs | Fully evidenced in IBD; **absent in asthma** |

---

## Visualizations (Session 002 gap filled)

| View | Nodes | Paths |
|---|---|---|
| **Full asthma graph** (pmid≥2 filter) | see manifest | `graph/visualizations/full_graph/` |
| **IBD master graph** | see manifest | `graph/visualizations/ibd_master_graph/` |

Session 002 seven views unchanged. Manifest updated: `graph/visualizations/visualization_manifest.json`

---

## Artifacts

| File | Content |
|---|---|
| `graph/novelty_audit.json` | `session_003` block with H-D001, H-C002 |
| `graph/cross_disease_motifs.json` | Motif comparison |
| `graph/ibd_knowledge_graph.json` | IBD cumulative graph |
| `reports/session_003_report.json` | Full JSON bundle |
| `reports/session_003_diff.md` | Session diff |
