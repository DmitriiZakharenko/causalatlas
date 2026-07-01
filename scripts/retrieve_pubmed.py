#!/usr/bin/env python3
"""Agent 1: Literature Retrieval - PubMed multi-strategy search."""
import json
import subprocess
import time
import urllib.parse
from pathlib import Path

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "research@example.com"
TOOL = "immuno_asthma_kg"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

QUERIES = {
    "mesh_core": '("Asthma"[MeSH Terms]) AND ("2021/01/01"[PDAT] : "2026/12/31"[PDAT])',
    "type2_immunity": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND (ILC2 OR "type 2 immunity" OR "IL-5" OR "IL-13" OR "IL-4") AND ("2021"[PDAT] : "2026"[PDAT])',
    "epithelial_barrier": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND ("airway epithelium" OR "IL-33" OR TSLP OR "epithelial alarmins") AND ("2021"[PDAT] : "2026"[PDAT])',
    "eosinophil": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND (eosinophil OR "IL-5 receptor") AND ("2021"[PDAT] : "2026"[PDAT])',
    "th2_cells": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND ("Th2" OR "T helper 2" OR GATA3 OR IL4R) AND ("2021"[PDAT] : "2026"[PDAT])',
    "clinical_trial": '("Asthma"[MeSH]) AND (clinical trial[pt] OR randomized controlled trial[pt]) AND ("2021"[PDAT] : "2026"[PDAT])',
    "single_cell": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND ("single-cell" OR scRNA-seq OR "single cell RNA") AND ("2021"[PDAT] : "2026"[PDAT])',
    "mast_cell": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND ("mast cell" OR tryptase) AND ("2021"[PDAT] : "2026"[PDAT])',
    "neutrophil": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND (neutrophil OR "type 2 low" OR "T2-low") AND ("2021"[PDAT] : "2026"[PDAT])',
    "systematic_review": '("Asthma"[MeSH]) AND (systematic review[pt] OR meta-analysis[pt] OR review[pt]) AND ("2021"[PDAT] : "2026"[PDAT])',
    "ilc2": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND (ILC2 OR "group 2 innate lymphoid") AND ("2021"[PDAT] : "2026"[PDAT])',
    "airway_remodeling": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND ("airway remodeling" OR fibrosis OR "smooth muscle") AND ("2021"[PDAT] : "2026"[PDAT])',
    "biologic_therapy": '("Asthma"[MeSH]) AND (dupilumab OR mepolizumab OR benralizumab OR tezepelumab OR omalizumab) AND ("2021"[PDAT] : "2026"[PDAT])',
    "memory_immunity": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND ("trained immunity" OR "immune memory" OR "tissue resident") AND ("2021"[PDAT] : "2026"[PDAT])',
    "bone_marrow": '("Asthma"[MeSH] OR asthma[Title/Abstract]) AND ("bone marrow" OR hematopoiesis OR "eosinophilopoiesis") AND ("2021"[PDAT] : "2026"[PDAT])',
}


def curl_get(url: str) -> str:
    result = subprocess.run(
        ["curl", "-s", url], capture_output=True, text=True, check=True
    )
    return result.stdout


def esearch(query: str, retmax: int = 40) -> dict:
    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "term": query,
            "retmax": retmax,
            "retmode": "json",
            "tool": TOOL,
            "email": EMAIL,
        }
    )
    data = json.loads(curl_get(f"{BASE}/esearch.fcgi?{params}"))
    return data["esearchresult"]


def efetch_batch(pmids: list[str]) -> str:
    """Fetch XML metadata for a batch of PMIDs."""
    id_str = ",".join(pmids)
    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "id": id_str,
            "retmode": "xml",
            "tool": TOOL,
            "email": EMAIL,
        }
    )
    return curl_get(f"{BASE}/efetch.fcgi?{params}")


def parse_pubmed_xml(xml_text: str) -> list[dict]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    papers = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        pmid_el = medline.find("PMID")
        pmid = pmid_el.text if pmid_el is not None else None

        art = medline.find("Article")
        title_el = art.find("ArticleTitle") if art is not None else None
        title = "".join(title_el.itertext()) if title_el is not None else ""

        abstract_parts = []
        if art is not None:
            abs_el = art.find("Abstract")
            if abs_el is not None:
                for t in abs_el.findall("AbstractText"):
                    label = t.get("Label", "")
                    text = "".join(t.itertext())
                    abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(abstract_parts)

        authors = []
        if art is not None:
            al = art.find("AuthorList")
            if al is not None:
                for a in al.findall("Author"):
                    last = a.findtext("LastName", "")
                    fore = a.findtext("ForeName", "")
                    authors.append(f"{fore} {last}".strip())

        journal_el = art.find("Journal") if art is not None else None
        journal = ""
        year = ""
        if journal_el is not None:
            journal = journal_el.findtext("Title", "")
            pub_date = journal_el.find("JournalIssue/PubDate")
            if pub_date is not None:
                year = pub_date.findtext("Year", "") or pub_date.findtext(
                    "MedlineDate", ""
                )[:4]

        article_ids = article.findall(".//ArticleId")
        doi = ""
        for aid in article_ids:
            if aid.get("IdType") == "doi":
                doi = aid.text or ""
                break

        pub_types = []
        if art is not None:
            ptl = art.find("PublicationTypeList")
            if ptl is not None:
                pub_types = [pt.text for pt in ptl.findall("PublicationType") if pt.text]

        mesh_terms = []
        mesh_list = medline.find("MeshHeadingList")
        if mesh_list is not None:
            for mh in mesh_list.findall("MeshHeading"):
                desc = mh.find("DescriptorName")
                if desc is not None and desc.text:
                    mesh_terms.append(desc.text)

        species = "unknown"
        mesh_lower = " ".join(mesh_terms).lower()
        title_abs = (title + " " + abstract).lower()
        if "humans" in mesh_lower or "human" in title_abs[:200]:
            species = "human"
        elif "mice" in mesh_lower or "mouse" in title_abs[:200]:
            species = "mouse"
        elif "mice" in mesh_lower and "humans" in mesh_lower:
            species = "human/mouse"

        papers.append(
            {
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi,
                "abstract": abstract,
                "mesh_terms": mesh_terms,
                "publication_types": pub_types,
                "species": species,
                "verified": False,
            }
        )
    return papers


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(exist_ok=True)

    all_pmids: set[str] = set()
    search_meta = {}

    for name, query in QUERIES.items():
        result = esearch(query, retmax=40)
        pmids = result.get("idlist", [])
        search_meta[name] = {
            "query": query,
            "total_count": result.get("count", "0"),
            "retrieved_pmids": pmids,
        }
        all_pmids.update(pmids)
        print(f"{name}: {result.get('count')} total, {len(pmids)} retrieved")
        time.sleep(0.35)

    pmid_list = sorted(all_pmids, key=int)
    print(f"\nUnique PMIDs: {len(pmid_list)}")

    with open(DATA_DIR / "search_results.json", "w") as f:
        json.dump(search_meta, f, indent=2)

    # Fetch metadata in batches of 50
    all_papers = []
    batch_size = 50
    for i in range(0, len(pmid_list), batch_size):
        batch = pmid_list[i : i + batch_size]
        xml = efetch_batch(batch)
        papers = parse_pubmed_xml(xml)
        all_papers.extend(papers)
        print(f"Fetched batch {i // batch_size + 1}: {len(papers)} papers")
        time.sleep(0.4)

    with open(DATA_DIR / "publications_raw.json", "w") as f:
        json.dump(all_papers, f, indent=2)

    print(f"Total papers fetched: {len(all_papers)}")


if __name__ == "__main__":
    main()
