# Asthma Mechanistic Knowledge Graph — Session 001

**Disease:** Asthma  
**Publication window:** 2021–2026 (5 years)  
**Session date:** 2026-07-01  
**Graph version:** 1.0.0  
**Primary artifact:** `graph/asthma_knowledge_graph.json`

---

## 1. Retrieved Papers

### Search strategy (Agent 1)

Fifteen complementary PubMed queries were executed via NCBI E-utilities:

| Strategy | Total in PubMed | Retrieved (top hits) |
|---|---|---|
| MeSH core (Asthma, 2021–2026) | 20,366 | 40 |
| Type 2 immunity (ILC2, IL-4/5/13) | 2,975 | 40 |
| Epithelial barrier (IL-33, TSLP) | 1,221 | 40 |
| Eosinophil / IL-5 | 5,634 | 40 |
| Th2 cells | 1,945 | 40 |
| Clinical trials | 813 | 40 |
| Single-cell | 362 | 40 |
| Mast cell | 488 | 40 |
| Neutrophil / T2-low | 1,876 | 40 |
| Systematic reviews | 3,764 | 40 |
| ILC2 | 345 | 40 |
| Airway remodeling | 3,426 | 40 |
| Biologic therapy | 1,284 | 40 |
| Memory / tissue-resident | 140 | 40 |
| Bone marrow / eosinophilopoiesis | 307 | 40 |

**Total unique PMIDs retrieved:** 449  
**Full metadata fetched:** 448 publications

All metadata stored in `data/publications_verified.json` including title, authors, journal, year, PMID, DOI, abstract, MeSH terms, publication type, and species annotation.

### Representative high-evidence publications

| PMID | Year | Title | Evidence level |
|---|---|---|---|
| [40184040](https://pubmed.ncbi.nlm.nih.gov/40184040/) | 2025 | Lung-resident memory CD4+ T cells are dependent on Batf3 | single_cell_study |
| [40866145](https://pubmed.ncbi.nlm.nih.gov/40866145/) | 2025 | ST2+ effector memory helper T cells… female-predominant airway inflammation | human_study |
| [42061467](https://pubmed.ncbi.nlm.nih.gov/42061467/) | 2026 | Group 2 innate lymphoid cells: Where are we 15 years out? | review |
| [41873839](https://pubmed.ncbi.nlm.nih.gov/41873839/) | 2026 | Dual clinical remission in severe asthma and CRSwNP: biologic therapies | review |
| [40454563](https://pubmed.ncbi.nlm.nih.gov/40454563/) | 2025 | ILC2 Diversity, Location, and Function in Pulmonary Disease | review |
| [40645203](https://pubmed.ncbi.nlm.nih.gov/40645203/) | 2025 | Multimorbidity on difficult-to-treat asthma (Lancet Respir Med) | human_cohort |

---

## 2. Verification Report (Agent 2)

| Metric | Value |
|---|---|
| Input papers | 448 |
| Accepted (Verified = TRUE) | 448 |
| Rejected | 0 |
| Duplicates removed | 0 |

**Verification criteria applied:**
- PMID exists (confirmed via PubMed efetch at retrieval)
- Title present and matches PubMed record
- DOI recorded when available (majority of papers)
- Authors, journal, year cross-checked against PubMed XML

Full per-paper report: `data/verification_report.json`

**Caveat:** Independent re-fetch verification was not repeated per-PMID in this session because all records originated from PubMed efetch. Future sessions should spot-check 5–10% of PMIDs.

---

## 3. Evidence Summary (Agent 3)

### Evidence level distribution (448 papers)

| Level | Count |
|---|---|
| Human study | 222 |
| Primary research | 137 |
| Single-cell study | 41 |
| Mouse study | 23 |
| In vitro | 21 |
| Organoid | 2 |
| Systematic review | 1 |
| Clinical trial | 1 |

### Species annotation

| Species | Count |
|---|---|
| Human | 242 |
| Unknown | 178 |
| Mouse | 28 |

### Temporal distribution

| Year | Count |
|---|---|
| 2025 | 18 |
| 2026 | 430 |

**Interpretation:** The retrieved corpus is heavily weighted toward 2026 publications because PubMed returns most-recent-first. The 2021–2024 portion is underrepresented in this initial retrieval batch. Future sessions should paginate deeper (retstart) per query to balance temporal coverage.

### Confidence scoring notes

- Systematic reviews/meta-analyses: 0.90–0.95
- Clinical trials: 0.85
- Human cohort studies: 0.60–0.80
- Single-cell studies: 0.75
- Mouse studies: ≤0.55 (translation uncertainty flagged)
- Small sample (n<30): −0.10 penalty

---

## 4. Mechanistic Extraction (Agent 4)

**Papers with ≥1 extracted edge:** 337 / 448 (75%)  
**Total raw edges extracted:** 1,195  
**Extraction methods:** Template matching (high precision) + causal verb patterns (lower precision)

### Top validated mechanistic chains (≥6 supporting PMIDs each)

```
Airway epithelium → IL-33 → ILC2 → IL-5 → Eosinophil → Airway remodeling
     (9 PMIDs)    (11)    (12)   (29)     (20)

Th2 cell → IL-4 → Th2 cell (positive feedback; 17 PMIDs)
Th2 cell → IL-13 → Mucus hypersecretion (13 PMIDs)
Th2 cell → IL-13 → Airway remodeling (6 PMIDs)

Allergen → Th2 cell (38 PMIDs)
IgE → Mast cell → Airway inflammation (15 + 31 PMIDs)

IL-5 → Bone marrow → Eosinophil (bone marrow axis; 10 PMIDs)

Batf3 → Dendritic cell → Tissue-resident memory T cell → Airway inflammation
        (PMID 40184040 + 7 PMIDs for TRM→inflammation)
```

### Therapeutic edges (biologics)

| Drug | Target | Relation | PMIDs |
|---|---|---|---|
| Tezepelumab | TSLP | suppresses | 10 |
| Dupilumab | Type 2 inflammation | suppresses | 9 |
| Mepolizumab | Eosinophil | suppresses | 20 |
| Benralizumab | Eosinophil | suppresses | 20* |
| Omalizumab | IgE | suppresses | 8 |

*\*Graph validation flag: Benralizumab→Eosinophil edge contains conflicting relation annotations (induces + suppresses) from pattern extraction noise. Canonical biology: suppresses/depletes. Edge retained with flag; not removed.*

Raw extraction log: `data/extraction_log.json`

---

## 5. Unified Knowledge Graph (Agent 5)

**Stored at:** `graph/asthma_knowledge_graph.json`

| Metric | Value |
|---|---|
| Total nodes | 947 |
| Total edges | 742 |
| Core biological edges (curated node set) | 74 |
| Strong edges (≥2 PMIDs or conf ≥0.7) | 46 |

### Node types

Cell, Cytokine, Molecule, Tissue, Clinical_phenotype, Pathway

### Edge types

activates, suppresses, induces, recruits, differentiates_into, maintains, creates_feedback_with

### Edge provenance

Every edge stores: supporting PMID(s), confidence score, species, publication year(s), evidence strength (weak/moderate/strong).

---

## 6. Graph Validation (Agent 6)

Full report: `graph/validation_report.json`

| Finding | Count | Action |
|---|---|---|
| Contradictory edge pairs | 0 | — |
| Weak edges (single PMID) | ~696 | Flagged, not removed |
| Single-paper nodes | ~870 | Flagged as poorly studied |
| Extraction noise nodes | Present | e.g., "They Have Strongly", "Mainly" — artifact of pattern parser; excluded from hypothesis generation |

**Known extraction artifacts to filter in future sessions:**
- Sentence-fragment nodes from aggressive regex parsing
- Drug→outcome edges with inverted relation polarity (Benralizumab)
- Preprint entries (e.g., PMID 40777291, bioRxiv) included but flagged with lower translational weight

---

## 7. Major Immune Architectures (Agent 7)

Ranked by composite score (completeness × PMID count × avg confidence):

### 1. Epithelial alarmin → ILC2 → Type 2 cytokine loop
- **Category:** barrier-immune loop
- **Path:** Airway epithelium → IL-33 → ILC2 → IL-5 → Eosinophil
- **Completeness:** 100% (4/4 edges)
- **Supporting PMIDs:** 41
- **Avg confidence:** 0.55
- **Key reference:** [42061467](https://pubmed.ncbi.nlm.nih.gov/42061467/) — "ILC2s produce high levels of IL5 and IL13 upon stimulation by epithelial-derived alarmins IL33, IL25, and TSLP"

### 2. Mast cell–IgE effector loop
- **Category:** effector loop
- **Path:** Allergen → IgE → Mast cell → Airway inflammation
- **Completeness:** 100% (3/3 edges)
- **Supporting PMIDs:** 36

### 3. IL-5 eosinophil amplification
- **Category:** immune amplification loop
- **Path:** ILC2 → IL-5 → Eosinophil → Airway inflammation
- **Completeness:** 67% (missing: Eosinophil → Airway inflammation as direct extracted edge; both nodes exist separately)
- **Supporting PMIDs:** 33

### 4. IL-4/IL-13 Th2 positive feedback
- **Category:** positive feedback loop
- **Path:** Th2 cell → IL-4 → Th2 cell
- **Completeness:** 100%
- **Supporting PMIDs:** 17

### 5. IL-13 remodeling axis
- **Category:** chronic inflammation loop
- **Path:** Th2 cell → IL-13 → Airway remodeling
- **Completeness:** 100%
- **Supporting PMIDs:** 13

### 6. Bone marrow eosinophilopoiesis axis
- **Category:** bone marrow communication
- **Path:** IL-5 → Bone marrow → Eosinophil
- **Completeness:** 100%
- **Supporting PMIDs:** 12

### 7. TSLP–dendritic–Th2 axis
- **Category:** immune education loop
- **Path:** Airway epithelium → TSLP → Dendritic cell → Th2 cell → IL-4
- **Completeness:** 100%
- **Supporting PMIDs:** 12

### 8. Tissue-resident memory chronicity loop
- **Category:** memory loop
- **Path:** Batf3 → Dendritic cell → Tissue-resident memory T cell → Airway inflammation
- **Completeness:** 67% (missing: Dendritic cell → TRM T cell)
- **Supporting PMIDs:** 7
- **Key reference:** [40184040](https://pubmed.ncbi.nlm.nih.gov/40184040/)

### 9–10. Biologic therapeutic interruption loops
- Tezepelumab → TSLP (50% path complete; 10 PMIDs)
- Dupilumab → Type 2 inflammation (50% path complete; 9 PMIDs)

---

## 8. Knowledge Gaps (Agent 8)

### Architecture-specific gaps

| Architecture | Missing edge | Status |
|---|---|---|
| IL-5 eosinophil amplification | Eosinophil → Airway inflammation | **Unknown** — nodes exist independently with strong evidence; direct causal edge not extracted from abstracts |
| Tissue-resident memory loop | Dendritic cell → Tissue-resident memory T cell | **Untested** — Batf3→cDC1 and TRM→inflammation supported; intermediate DC→TRM priming step not explicit in retrieved abstracts |
| Anti-TSLP therapy | TSLP → Type 2 inflammation | **Unknown** — tezepelumab→TSLP well supported; downstream edge inferred but not directly extracted |
| Anti-IL-4R therapy | Type 2 inflammation → Airway inflammation | **Unknown** — logical but not directly extracted as single edge |

### Poorly studied nodes (single-PMID support)

- **Batf3** — only PMID 40184040 in core set; critical for TRM chronicity hypothesis
- **IL-25** — 7 PMIDs for IL-25→ILC2; less studied than IL-33 pathway
- **Trained immunity** — minimal direct asthma edges in this corpus

### Contradictory evidence

No directly contradictory edge pairs detected in core biological subgraph. **INSUFFICIENT EVIDENCE** for formal conflict resolution on T2-high vs T2-low endotype dominance — both neutrophilic (40 PMIDs) and eosinophilic (66 PMIDs) inflammation edges are represented.

---

## 9. Generated Hypotheses (Agent 9)

*Generated only from validated graph + identified gaps. No invented biology.*

---

### Hypothesis H1: cDC1-dependent priming is required for establishment of lung CD4+ tissue-resident memory T cells that sustain chronic (but not acute) allergic airway inflammation

**Mechanistic rationale:**  
Batf3 is required for cDC1 development. Batf3-deficient mice show normal acute HDM asthma but fail to develop lung CD4+ TRM cells (Cxcr6+) and have attenuated chronic inflammation and AHR ([40184040](https://pubmed.ncbi.nlm.nih.gov/40184040/)). TRM cells independently drive airway inflammation ([40184040](https://pubmed.ncbi.nlm.nih.gov/40184040/), [40866145](https://pubmed.ncbi.nlm.nih.gov/40866145/)).

**Supporting evidence:**
- Batf3 → Dendritic cell (cDC1): PMID 40184040
- TRM T cell → Airway inflammation: 7 PMIDs
- ST2+ effector memory T cells sustain long-term exacerbation: PMID 40866145

**Missing evidence:**
- Direct edge: Dendritic cell → TRM T cell priming (gap)
- Human validation of Batf3/cDC1 axis in asthma
- Whether Cxcr6+ TRM are the effector population in chronic human asthma

**Predicted consequence:**  
Conditional deletion of Batf3 in cDC1 (Xcr1-Cre) after initial sensitization will prevent TRM accumulation and abolish chronic (≥8 week) but not acute (≤2 week) HDM-induced AHR.

**Alternative explanations:**
- Batf3 affects non-DC lineages indirectly
- TRM defect is compensatable by circulating effector T cells in acute models
- Cxcr6 marks correlation not causation

**Confidence:** Medium (0.55)  
**Novelty estimate:** Low — extends established TRM-chronicity concept with specific cDC1 dependency

---

### Hypothesis H2: IL-33-driven ILC2 activation couples local airway inflammation to bone marrow eosinophilopoiesis via IL-5, creating a feed-forward loop between tissue and systemic compartments

**Mechanistic rationale:**  
Complete epithelial alarmin→ILC2→IL-5→Eosinophil architecture (41 PMIDs). IL-5→Bone marrow→Eosinophil axis independently supported (12 PMIDs). Gap: whether IL-33 stimulation concurrently activates both local ILC2 and systemic IL-5-driven marrow output.

**Supporting evidence:**
- Airway epithelium → IL-33: 9 PMIDs
- IL-33 → ILC2: 11 PMIDs
- ILC2 → IL-5: 12 PMIDs
- IL-5 → Bone marrow: supported in graph
- Bone marrow → Eosinophil: 10 PMIDs

**Missing evidence:**
- Simultaneous measurement of airway IL-33, marrow eosinophil progenitors, and blood eosinophils in same subjects
- Causal blockade of ILC2 specifically (not global anti-IL-5) on marrow output

**Predicted consequence:**  
Anti-IL-33 or ILC2 depletion will reduce both airway IL-5 AND bone marrow eosinophil progenitor frequency, while anti-IL-5 alone will deplete mature eosinophils without fully reversing ILC2 activation.

**Alternative explanations:**
- Th2 cells (not ILC2) are primary IL-5 source for marrow signaling
- Bone marrow eosinophilopoiesis is IL-5-independent in humans

**Confidence:** Medium-high (0.62)  
**Novelty estimate:** Low — integrative framing of two well-supported sub-architectures

---

### Hypothesis H3: TSLP blockade with tezepelumab interrupts upstream epithelial signaling before ILC2/Th2 bifurcation, producing broader Type 2 suppression than downstream anti-IL-5 alone

**Mechanistic rationale:**  
Tezepelumab → TSLP (10 PMIDs). TSLP → Dendritic cell → Th2 axis complete (12 PMIDs). Epithelial alarmin loop complete via IL-33/IL-25 (41 PMIDs). Tezepelumab path only 50% complete in graph (missing TSLP → Type 2 inflammation direct edge).

**Supporting evidence:**
- [41873839](https://pubmed.ncbi.nlm.nih.gov/41873839/): comparative biologic review including tezepelumab WAYPOINT trial
- Tezepelumab suppresses TSLP: 10 PMIDs
- Dupilumab suppresses Type 2 inflammation: 9 PMIDs

**Missing evidence:**
- Head-to-head tezepelumab vs mepolizumab with matched baseline T2 biomarkers in same trial
- Direct TSLP → Type 2 inflammation edge in graph (INSUFFICIENT EVIDENCE as extracted edge)

**Predicted consequence:**  
Tezepelumab will reduce ILC2 AND Th2-derived cytokines simultaneously; mepolizumab will reduce eosinophils without normalizing IL-13 or FeNO.

**Alternative explanations:**
- Tezepelumab effects are primarily via IL-33 cross-talk, not TSLP alone
- Clinical differences are due to patient selection, not mechanism

**Confidence:** Medium (0.58)  
**Novelty estimate:** Low — aligns with published trial data; mechanistic comparison not novel

---

### Hypothesis H4: ST2+ (IL-33R+) effector memory CD4+ T cells represent a human parallel to mouse lung TRM cells in sustaining long-term asthma exacerbations

**Mechanistic rationale:**  
PMID 40866145 identifies ST2+ effector memory helper T cells as drivers of long-term exacerbation with female predominance. ST2 is IL-33 receptor. IL-33 → ILC2 well established, but ST2+ T cells as IL-33-responsive memory population in chronic human asthma is less connected in graph.

**Supporting evidence:**
- PMID 40866145: ST2+ T cells → long-term exacerbation
- IL-33 → ILC2: 11 PMIDs
- TRM → Airway inflammation: 7 PMIDs

**Missing evidence:**
- Whether ST2+ EM T cells are tissue-resident (CD69+CD103+) in human lung
- Direct IL-33 responsiveness of these T cells vs ILC2 in human tissue
- Cross-species equivalence of mouse TRM (PMID 40184040) and human ST2+ EM T cells

**Predicted consequence:**  
ST2+ CD4+ T cells in human bronchial biopsies will correlate with exacerbation frequency independent of blood eosinophil count; anti-IL-33 will reduce this population.

**Alternative explanations:**
- ST2 is marker not driver
- Female predominance reflects hormonal confounders

**Confidence:** Low-medium (0.48)  
**Novelty estimate:** Medium — cross-linking two supported but disconnected findings

---

## 10. Independent Peer Review (Agent 10)

### Hypothesis H1 — cDC1/TRM chronicity

| Reviewer | Role | Decision | Key criticism |
|---|---|---|---|
| A | Immunologist | **ACCEPT** | Batf3-cDC1-TRM chain is biologically coherent; acute vs chronic dissociation is compelling discriminative prediction |
| B | Systems biologist | **UNCERTAIN** | Graph completeness only 67%; DC→TRM edge is inferred not extracted; single mouse paper anchors Batf3 node |
| C | Nature Immunology editor | **UNCERTAIN** | Needs human relevance; would require confirmation that cDC1 are necessary for TRM in human lung explants |

**Consensus:** UNCERTAIN → conditional acceptance pending DC→TRM edge validation

---

### Hypothesis H2 — IL-33/ILC2/bone marrow coupling

| Reviewer | Role | Decision | Key criticism |
|---|---|---|---|
| A | Immunologist | **ACCEPT** | IL-5 bone marrow axis well established; ILC2 as IL-5 source in asthma widely accepted |
| B | Systems biologist | **ACCEPT** | Two complete sub-architectures; feed-forward prediction is testable with clear falsification |
| C | Nature Immunology editor | **ACCEPT** | Low novelty but high rigor; publishable as confirmatory systems study |

**Consensus:** ACCEPT

---

### Hypothesis H3 — Tezepelumab upstream breadth

| Reviewer | Role | Decision | Key criticism |
|---|---|---|---|
| A | Immunologist | **ACCEPT** | Consistent with NAVIGATOR/WAYPOINT data |
| B | Systems biologist | **REJECT** | Not a novel hypothesis; is already clinical consensus; TSLP→T2 edge missing from graph |
| C | Nature Immunology editor | **REJECT** | Descriptive comparison of approved drugs; insufficient mechanistic novelty |

**Consensus:** REJECT (already established; fails novelty threshold for hypothesis product)

---

### Hypothesis H4 — ST2+ EM T cells as human TRM parallel

| Reviewer | Role | Decision | Key criticism |
|---|---|---|---|
| A | Immunologist | **UNCERTAIN** | ST2+ T cells and TRM are not necessarily equivalent populations |
| B | Systems biologist | **REJECT** | Cross-species mapping without shared markers is speculative; only 1 PMID anchors ST2+ EM phenotype |
| C | Nature Immunology editor | **REJECT** | INSUFFICIENT EVIDENCE for TRM equivalence; single primary paper |

**Consensus:** REJECT

---

## 11. Accepted Hypotheses

| ID | Hypothesis | Confidence | Status |
|---|---|---|---|
| **H2** | IL-33/ILC2/IL-5 couples airway to bone marrow eosinophilopoiesis | 0.62 | **ACCEPTED** |
| **H1** | cDC1 (Batf3-dependent) required for lung TRM sustaining chronic asthma | 0.55 | **CONDITIONALLY ACCEPTED** |

---

## 12. Experimental Validation Roadmap (Agent 11)

### H2: IL-33/ILC2/bone marrow eosinophilopoiesis coupling

**Model:** House dust mite (HDM) sensitized C57BL/6 mice, 6-week chronic protocol + parallel human severe asthma cohort (n≥50, eosinophilic phenotype)

| Experiment | Method | Predicted outcome | Falsification criterion |
|---|---|---|---|
| E2-1 | Anti-IL-33 mAb vs anti-IL-5 (mepolizumab analog) in chronic HDM model | Anti-IL-33 reduces ILC2 frequency, airway IL-5, AND marrow eosinophil progenitors; anti-IL-5 only reduces blood/marrow mature eosinophils | Marrow progenitors unchanged by anti-IL-33 |
| E2-2 | Single-cell RNA-seq of lung + bone marrow at weeks 2, 4, 6 | ILC2 expansion precedes marrow eosinophil progenitor increase; Il5 transcript peaks in ILC2 before marrow EoP expansion | Th2 cells are primary Il5 source temporally |
| E2-3 | ILC2 depletion (Il7r-Cre × DT receptor) | Loss of ILC2 abolishes both airway and marrow eosinophil expansion | Marrow eosinophilopoiesis persists without ILC2 |
| E2-4 | Human observational: FeNO, blood eosinophils, IL-33 (sputum), marrow MRI/sampling if ethically feasible | Positive correlation between sputum IL-33 and eosinophil progenitor frequency | No correlation in human cohort |

**Negative controls:** Isotype antibody; IL-33 blockade in ILC2-deficient mice  
**Best readout:** Flow cytometry (lung ILC2, marrow EoP), scRNA-seq, serum/sputum IL-5

---

### H1: cDC1-dependent TRM chronicity (conditional)

**Model:** Batf3⁻/⁻ and Xcr1-Cre × Batf3^fl/fl mice; acute (2-week) vs chronic (8-week) HDM

| Experiment | Method | Predicted outcome | Falsification criterion |
|---|---|---|---|
| E1-1 | Longitudinal HDM: measure lung CD4+ CD69+ CD103+ Cxcr6+ cells | TRM accumulation only in WT chronic model; absent in Batf3⁻/⁻ | TRM develop normally in Batf3⁻/⁻ |
| E1-2 | scRNA-seq lung T cells at acute vs chronic timepoints | Cxcr6+ TRM cluster absent in Batf3⁻/⁻ chronic | Different TRM subset affected |
| E1-3 | Adoptive transfer of OT-II cells + DC subsets (cDC1 vs cDC2) | cDC1-primed T cells form TRM; cDC2-primed do not | cDC2 sufficient for TRM |
| E1-4 | Human bronchial biopsy: cDC1 (BDCA3+) and TRM (CD69+CD103+CD4+) in chronic vs newly diagnosed asthma | Positive correlation cDC1 abundance ↔ TRM in chronic asthma | No correlation in humans |

**Negative controls:** Batf3⁻/⁻ with adoptive WT cDC1 rescue  
**Falsification:** If acute and chronic phenotypes are equally impaired in Batf3⁻/⁻, hypothesis rejected

---

## Long-Term Memory Notes

- Graph stored at `graph/asthma_knowledge_graph.json` — cumulative, do not overwrite evidence
- Next session priorities:
  1. Paginate PubMed searches to retrieve 2021–2024 papers (temporal bias correction)
  2. Filter extraction noise nodes from pattern parser
  3. Fix Benralizumab relation polarity
  4. Merge new publications without overwriting existing edge PMID lists
  5. Validate H1 DC→TRM edge with targeted literature search

---

*All PMIDs traceable to PubMed. No papers, findings, or mechanisms were invented. Uncertainty explicitly preserved where evidence is incomplete.*
