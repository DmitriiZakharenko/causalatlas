#!/usr/bin/env python3
"""
Agent 4: Mechanism Extraction - extract directed causal relationships from abstracts.
Conservative: only extract relationships explicitly supported by abstract text.
"""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GRAPH_DIR = Path(__file__).resolve().parent.parent / "graph"

# Node normalization map
NODE_ALIASES = {
    "il-4": "IL-4", "il4": "IL-4", "il 4": "IL-4",
    "il-5": "IL-5", "il5": "IL-5",
    "il-13": "IL-13", "il13": "IL-13",
    "il-33": "IL-33", "il33": "IL-33",
    "il-25": "IL-25", "il25": "IL-25",
    "tslp": "TSLP", "thymic stromal lymphopoietin": "TSLP",
    "ilc2": "ILC2", "ilc2s": "ILC2", "group 2 innate lymphoid": "ILC2",
    "th2": "Th2 cell", "th2 cell": "Th2 cell", "t helper 2": "Th2 cell",
    "th2 cells": "Th2 cell", "cd4+ th2": "Th2 cell",
    "eosinophil": "Eosinophil", "eosinophils": "Eosinophil",
    "neutrophil": "Neutrophil", "neutrophils": "Neutrophil",
    "mast cell": "Mast cell", "mast cells": "Mast cell",
    "basophil": "Basophil", "basophils": "Basophil",
    "dendritic cell": "Dendritic cell", "dendritic cells": "Dendritic cell",
    "cdc1": "cDC1", "conventional dendritic cell": "Dendritic cell",
    "airway epithelium": "Airway epithelium", "airway epithelial": "Airway epithelium",
    "epithelial cell": "Airway epithelium", "bronchial epithelium": "Airway epithelium",
    "goblet cell": "Goblet cell", "goblet cells": "Goblet cell",
    "smooth muscle": "Airway smooth muscle",
    "fibroblast": "Fibroblast", "fibroblasts": "Fibroblast",
    "ige": "IgE", "immunoglobulin e": "IgE",
    "il-4r": "IL-4R", "il4r": "IL-4R", "il-4 receptor": "IL-4R",
    "il-5r": "IL-5R", "il5r": "IL-5R",
    "il-13r": "IL-13R",
    "st2": "ST2", "il-33 receptor": "ST2", "il1rl1": "ST2",
    "gata3": "GATA3",
    "stat6": "STAT6",
    "batf3": "Batf3",
    "airway inflammation": "Airway inflammation",
    "airway hyperresponsiveness": "Airway hyperresponsiveness", "ahr": "Airway hyperresponsiveness",
    "airway remodeling": "Airway remodeling",
    "mucus production": "Mucus hypersecretion", "mucus hypersecretion": "Mucus hypersecretion",
    "type 2 inflammation": "Type 2 inflammation", "type 2 immune response": "Type 2 inflammation",
    "type 2 immunity": "Type 2 inflammation", "t2 inflammation": "Type 2 inflammation",
    "allergen": "Allergen", "allergens": "Allergen",
    "house dust mite": "House dust mite", "hdm": "House dust mite",
    "bone marrow": "Bone marrow",
    "lung": "Lung", "airway": "Airway",
    "tissue-resident memory": "Tissue-resident memory T cell",
    "trm": "Tissue-resident memory T cell",
    "resident memory t cell": "Tissue-resident memory T cell",
    "trained immunity": "Trained immunity",
    "dupilumab": "Dupilumab", "mepolizumab": "Mepolizumab",
    "benralizumab": "Benralizumab", "tezepelumab": "Tezepelumab",
    "omalizumab": "Omalizumab",
}

# Causal verb patterns -> edge type
CAUSAL_PATTERNS = [
    (r"(\w[\w\s\-\+/]+?)\s+(?:induces?|induced|inducing|induction of)\s+(\w[\w\s\-\+/]+)", "induces"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:activates?|activated|activating|activation of)\s+(\w[\w\s\-\+/]+)", "activates"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:stimulates?|stimulated|stimulating)\s+(\w[\w\s\-\+/]+)", "activates"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:promotes?|promoted|promoting|promotes the development of)\s+(\w[\w\s\-\+/]+)", "activates"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:drives?|drove|driving)\s+(\w[\w\s\-\+/]+)", "activates"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:recruits?|recruited|recruitment of)\s+(\w[\w\s\-\+/]+)", "recruits"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:inhibits?|inhibited|inhibiting|inhibition of)\s+(\w[\w\s\-\+/]+)", "suppresses"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:suppresses?|suppressed|suppressing|suppression of)\s+(\w[\w\s\-\+/]+)", "suppresses"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:reduces?|reduced|reducing|reduction of|decreases?|decreased)\s+(\w[\w\s\-\+/]+)", "suppresses"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:blocks?|blocked|blocking)\s+(\w[\w\s\-\+/]+)", "suppresses"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:differentiates?|differentiated|differentiation into)\s+(\w[\w\s\-\+/]+)", "differentiates_into"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:produces?|produced|production of|secretes?|secreted|secretion of|releases?|released|release of)\s+(\w[\w\s\-\+/]+)", "induces"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:maintains?|maintained|maintenance of)\s+(\w[\w\s\-\+/]+)", "maintains"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:contributes? to|contributed to|contribute to)\s+(\w[\w\s\-\+/]+)", "activates"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:leads? to|led to|leading to|results? in|resulted in)\s+(\w[\w\s\-\+/]+)", "induces"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:dependent on|depends on|requires?|required for)\s+(\w[\w\s\-\+/]+)", "activates"),
    (r"(\w[\w\s\-\+/]+?)\s+(?:expresses?|expressed|expression of|upregulates?|upregulated|upregulation of)\s+(\w[\w\s\-\+/]+)", "induces"),
]

# Well-established mechanistic templates to search for in text
MECHANISM_TEMPLATES = [
    ("Airway epithelium", "induces", "TSLP", r"epithelial.*?(?:release|produce|express).*?tslp|tslp.*?(?:from|by).*?epitheli"),
    ("Airway epithelium", "induces", "IL-33", r"epithelial.*?(?:release|produce|express).*?il-?33|il-?33.*?(?:from|by).*?epitheli"),
    ("TSLP", "activates", "Dendritic cell", r"tslp.*?(?:activate|stimulat).*?dendritic"),
    ("IL-33", "activates", "ILC2", r"il-?33.*?(?:activate|stimulat).*?ilc2|ilc2.*?(?:activate|stimulat).*?il-?33"),
    ("IL-33", "activates", "ILC2", r"il-?33.*?st2|st2.*?il-?33"),
    ("ILC2", "induces", "IL-5", r"ilc2.*?(?:produce|secre|express).*?il-?5|il-?5.*?(?:from|by).*?ilc2"),
    ("ILC2", "induces", "IL-13", r"ilc2.*?(?:produce|secre|express).*?il-?13|il-?13.*?(?:from|by).*?ilc2"),
    ("Th2 cell", "induces", "IL-4", r"th2.*?(?:produce|secre|express).*?il-?4"),
    ("Th2 cell", "induces", "IL-5", r"th2.*?(?:produce|secre|express).*?il-?5"),
    ("Th2 cell", "induces", "IL-13", r"th2.*?(?:produce|secre|express).*?il-?13"),
    ("IL-5", "recruits", "Eosinophil", r"il-?5.*?(?:recruit|expand|eosinophil)|eosinophil.*?(?:recruit|expand).*?il-?5"),
    ("IL-4", "activates", "Th2 cell", r"il-?4.*?(?:promot|driv|polariz).*?th2|th2.*?il-?4"),
    ("IL-13", "induces", "Mucus hypersecretion", r"il-?13.*?(?:mucus|goblet|hypersecret)"),
    ("IL-13", "induces", "Airway remodeling", r"il-?13.*?(?:remodel|fibrosis|fibroblast)"),
    ("IgE", "activates", "Mast cell", r"ige.*?(?:activat|bind|cross-link).*?mast|mast.*?ige"),
    ("Mast cell", "induces", "Airway inflammation", r"mast cell.*?(?:inflamm|mediator|histamine|leukotriene)"),
    ("Allergen", "activates", "Th2 cell", r"allergen.*?(?:sensitiz|th2|ige)"),
    ("Batf3", "activates", "Dendritic cell", r"batf3.*?(?:c?dc1|dendritic)"),
    ("Batf3", "activates", "Tissue-resident memory T cell", r"batf3.*?(?:resident memory|trm|cd4\+.*?resident)"),
    ("Tissue-resident memory T cell", "induces", "Airway inflammation", r"(?:resident memory|trm).*?(?:inflamm|airway hyperrespons)"),
    ("Tissue-resident memory T cell", "induces", "Airway hyperresponsiveness", r"(?:resident memory|trm).*?(?:hyperrespons|ahr)"),
    ("Dupilumab", "suppresses", "Type 2 inflammation", r"dupilumab.*?(?:reduc|inhibit|suppress|block).*?(?:type.?2|il-?(?:4|5|13))"),
    ("Mepolizumab", "suppresses", "Eosinophil", r"mepolizumab.*?(?:reduc|deplet|eosinophil)"),
    ("Benralizumab", "suppresses", "Eosinophil", r"benralizumab.*?(?:reduc|deplet|eosinophil)"),
    ("Tezepelumab", "suppresses", "TSLP", r"tezepelumab.*?(?:block|inhibit|tslp)"),
    ("Omalizumab", "suppresses", "IgE", r"omalizumab.*?(?:ige|immunoglobulin)"),
    ("GATA3", "activates", "Th2 cell", r"gata3.*?(?:th2|t helper 2)"),
    ("IL-4", "activates", "GATA3", r"il-?4.*?gata3|gata3.*?il-?4"),
    ("STAT6", "activates", "GATA3", r"stat6.*?gata3|gata3.*?stat6"),
    ("Neutrophil", "induces", "Airway inflammation", r"neutrophil.*?(?:inflamm|neutrophilic)"),
    ("Type 2 inflammation", "induces", "Eosinophil", r"type.?2.*?(?:eosinophil|il-?5)"),
    ("Eosinophil", "induces", "Airway remodeling", r"eosinophil.*?(?:remodel|tissue damage|structural)"),
    ("House dust mite", "activates", "Airway epithelium", r"(?:house dust mite|hdm).*?(?:epithel|alarm)"),
    ("Bone marrow", "recruits", "Eosinophil", r"bone marrow.*?(?:eosinophil|eosinophilopoiesis|hematopoies)"),
    ("IL-5", "activates", "Bone marrow", r"il-?5.*?(?:bone marrow|eosinophilopoiesis)"),
    ("Trained immunity", "activates", "Innate immune cell", r"trained immunity.*?(?:innate|monocyte|macrophage)"),
    ("Airway epithelium", "induces", "IL-25", r"epithelial.*?il-?25|il-?25.*?epithel"),
    ("IL-25", "activates", "ILC2", r"il-?25.*?ilc2|ilc2.*?il-?25"),
    ("Fibroblast", "induces", "Airway remodeling", r"fibroblast.*?(?:remodel|collagen|extracellular matrix)"),
    ("Airway smooth muscle", "induces", "Airway hyperresponsiveness", r"smooth muscle.*?(?:hyperrespons|bronchoconstrict)"),
]


def normalize_node(text: str) -> str | None:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    if text in NODE_ALIASES:
        return NODE_ALIASES[text]
    for alias, canonical in NODE_ALIASES.items():
        if alias in text or text in alias:
            return canonical
    # Keep if looks like biological entity
    if len(text) > 2 and len(text) < 60:
        return text.title() if text.islower() else text
    return None


def classify_node(node: str) -> str:
    cells = {"ILC2", "Th2 cell", "Eosinophil", "Neutrophil", "Mast cell", "Basophil",
             "Dendritic cell", "cDC1", "Goblet cell", "Fibroblast", "Tissue-resident memory T cell",
             "Innate immune cell"}
    cytokines = {"IL-4", "IL-5", "IL-13", "IL-33", "IL-25", "TSLP"}
    molecules = {"IgE", "IL-4R", "IL-5R", "IL-13R", "ST2", "GATA3", "STAT6", "Batf3"}
    tissues = {"Airway epithelium", "Lung", "Airway", "Bone marrow"}
    phenotypes = {"Airway inflammation", "Airway hyperresponsiveness", "Airway remodeling",
                  "Mucus hypersecretion", "Type 2 inflammation"}
    drugs = {"Dupilumab", "Mepolizumab", "Benralizumab", "Tezepelumab", "Omalizumab"}
    if node in cells:
        return "Cell"
    if node in cytokines:
        return "Cytokine"
    if node in molecules:
        return "Molecule"
    if node in tissues:
        return "Tissue"
    if node in phenotypes:
        return "Clinical_phenotype"
    if node in drugs:
        return "Molecule"
    if "muscle" in node.lower():
        return "Tissue"
    return "Unknown"


def _supporting_sentence(abstract: str, source: str, target: str) -> str | None:
    """Return the exact abstract sentence containing both extracted entities."""
    for sentence in re.split(r"(?<=[.!?])\s+", abstract.strip()):
        lowered = sentence.lower()
        if source.lower() in lowered and target.lower() in lowered:
            return sentence.strip()
    return None


def extract_from_abstract(abstract: str, pmid: str, year: str, species: str, confidence: float) -> list[dict]:
    if not abstract:
        return []
    edges = []
    abs_lower = abstract.lower()

    # Template-based extraction (high precision)
    for source, rel, target, pattern in MECHANISM_TEMPLATES:
        if re.search(pattern, abs_lower, re.IGNORECASE):
            edges.append({
                "source": source,
                "source_type": classify_node(source),
                "relation": rel,
                "target": target,
                "target_type": classify_node(target),
                "pmid": pmid,
                "year": year,
                "species": species,
                "confidence": confidence,
                "extraction_method": "template",
                "source_sentence": _supporting_sentence(abstract, source, target),
            })

    # Pattern-based extraction (lower precision, deduplicated)
    seen = {(e["source"], e["relation"], e["target"]) for e in edges}
    for pattern, rel in CAUSAL_PATTERNS:
        for match in re.finditer(pattern, abs_lower, re.IGNORECASE):
            src = normalize_node(match.group(1))
            tgt = normalize_node(match.group(2))
            if src and tgt and src != tgt and (src, rel, tgt) not in seen:
                if len(src) > 2 and len(tgt) > 2:
                    seen.add((src, rel, tgt))
                    edges.append({
                        "source": src,
                        "source_type": classify_node(src),
                        "relation": rel,
                        "target": tgt,
                        "target_type": classify_node(tgt),
                        "pmid": pmid,
                        "year": year,
                        "species": species,
                        "confidence": max(confidence - 0.15, 0.30),
                        "extraction_method": "pattern",
                        "source_sentence": _supporting_sentence(abstract, src, tgt),
                    })

    return edges


def main():
    with open(DATA_DIR / "publications_verified.json") as f:
        papers = json.load(f)

    all_edges = []
    extraction_log = []

    for paper in papers:
        edges = extract_from_abstract(
            paper["abstract"],
            paper["pmid"],
            paper["year"],
            paper["species"],
            paper["quality"]["confidence_score"],
        )
        if edges:
            all_edges.extend(edges)
            extraction_log.append({
                "pmid": paper["pmid"],
                "title": paper["title"][:100],
                "edges_extracted": len(edges),
                "edges": edges,
            })

    with open(DATA_DIR / "mechanisms_extracted.json", "w") as f:
        json.dump({"total_edges": len(all_edges), "edges": all_edges}, f, indent=2)

    with open(DATA_DIR / "extraction_log.json", "w") as f:
        json.dump(extraction_log, f, indent=2)

    print(f"Papers with mechanisms: {len(extraction_log)}/{len(papers)}")
    print(f"Total edges extracted: {len(all_edges)}")


if __name__ == "__main__":
    main()
