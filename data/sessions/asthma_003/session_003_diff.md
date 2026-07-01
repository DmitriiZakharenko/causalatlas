# Session 003 Diff

## Unchanged
- Asthma `knowledge_graph.json`: 949 nodes / 753 edges (no edge or corpus edits)
- TSLP→T2 and Eosinophil→inflammation gaps remain closed

## New hypotheses (Agent 10 → 9 → 11 → 12)

| ID | Class | Specific prediction | Agent 11 |
|---|---|---|---|
| **H-D001** | D | Cxcr6+ TRM adoptive transfer restores chronic HDM in Batf3⁻/⁻ | ACCEPT |
| **H-C002** | C | Biphasic inflammatory crossover week under harmonized HDM | ACCEPT |

## Cross-disease
- New graph: `graph/ibd_knowledge_graph.json` (266 PMIDs, 11 nodes, 14 edges)
- Motif report: `graph/cross_disease_motifs.json`
- Key finding: ILC3→IL-22→barrier fully evidenced in IBD (84 PMIDs), absent in asthma; epithelial→ILC2→T2 fully in asthma (190 PMIDs), absent in IBD

## Visualizations added
- `graph/visualizations/full_graph/` — full asthma graph (pmid≥2 filter, 63 nodes)
- `graph/visualizations/ibd_master_graph/` — IBD graph (10 nodes)
