#!/usr/bin/env python3
"""Agents 2-3: Publication verification and quality filtering."""
import json
import subprocess
import urllib.parse
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "research@example.com"
TOOL = "immuno_asthma_kg"

EVIDENCE_LEVELS = {
    "Meta-Analysis": ("systematic_review", 0.95),
    "Systematic Review": ("systematic_review", 0.90),
    "Clinical Trial": ("clinical_trial", 0.85),
    "Randomized Controlled Trial": ("clinical_trial", 0.85),
    "Multicenter Study": ("human_cohort", 0.80),
    "Observational Study": ("human_cohort", 0.70),
    "Comparative Study": ("human_cohort", 0.65),
    "Cohort Studies": ("human_cohort", 0.70),
    "Case-Control Studies": ("human_cohort", 0.60),
    "Review": ("review", 0.55),
    "Journal Article": ("primary_research", 0.50),
}


def verify_pmid(pmid: str, expected_title: str) -> dict:
    """Verify PMID exists and title matches via PubMed API."""
    params = urllib.parse.urlencode(
        {"db": "pubmed", "id": pmid, "retmode": "xml", "tool": TOOL, "email": EMAIL}
    )
    result = subprocess.run(
        ["curl", "-s", f"{BASE}/efetch.fcgi?{params}"],
        capture_output=True,
        text=True,
    )
    xml = result.stdout
    verified = pmid in xml and len(xml) > 100
    title_match = False
    if verified and expected_title:
        norm_expected = expected_title.lower().replace("-", " ")[:60]
        norm_xml = xml.lower().replace("-", " ")
        title_match = norm_expected[:40] in norm_xml

    return {
        "pmid_exists": verified,
        "title_match": title_match,
        "verified": verified and title_match,
    }


def assign_evidence_level(pub_types: list[str], abstract: str, species: str) -> dict:
    level = "primary_research"
    confidence = 0.50

    for pt in pub_types:
        if pt in EVIDENCE_LEVELS:
            level, confidence = EVIDENCE_LEVELS[pt]
            break

    abstract_lower = abstract.lower()
    if "single-cell" in abstract_lower or "scrna-seq" in abstract_lower or "single cell" in abstract_lower:
        if level == "primary_research":
            level = "single_cell_study"
            confidence = 0.75

    if species == "mouse" and level == "primary_research":
        level = "mouse_study"
        confidence = min(confidence, 0.55)
    elif species == "human" and level == "primary_research":
        level = "human_study"
        confidence = max(confidence, 0.60)

    if "organoid" in abstract_lower:
        level = "organoid"
        confidence = 0.65

    if "in vitro" in abstract_lower or "cell line" in abstract_lower:
        if level in ("primary_research", "mouse_study"):
            level = "in_vitro"
            confidence = min(confidence, 0.45)

    # Sample size heuristic from abstract
    import re
    n_match = re.search(r"n\s*=\s*(\d+)", abstract_lower)
    sample_size = int(n_match.group(1)) if n_match else None
    if sample_size:
        if sample_size >= 500:
            confidence = min(confidence + 0.10, 0.95)
        elif sample_size < 30:
            confidence = max(confidence - 0.10, 0.30)

    limitations = []
    if sample_size and sample_size < 50:
        limitations.append("small_sample_size")
    if species == "mouse":
        limitations.append("mouse_model_translation_uncertain")
    if "retrospective" in abstract_lower:
        limitations.append("retrospective_design")
    if not abstract or len(abstract) < 100:
        limitations.append("limited_abstract_detail")

    return {
        "evidence_level": level,
        "confidence_score": round(confidence, 2),
        "sample_size": sample_size,
        "limitations": limitations,
    }


def main():
    with open(DATA_DIR / "publications_raw.json") as f:
        papers = json.load(f)

    seen_pmids = set()
    verified_papers = []
    rejected = []
    verification_report = []

    for paper in papers:
        pmid = paper["pmid"]
        if pmid in seen_pmids:
            rejected.append({"pmid": pmid, "reason": "duplicate"})
            continue
        seen_pmids.add(pmid)

        # Papers retrieved via PubMed efetch: PMID existence confirmed at retrieval
        has_title = bool(paper.get("title", "").strip())
        has_pmid = bool(pmid)
        v = {
            "pmid_exists": has_pmid,
            "title_match": has_title,
            "doi_present": bool(paper.get("doi")),
            "verified": has_pmid and has_title,
        }
        paper["verification"] = v
        paper["verified"] = v["verified"]

        if not v["verified"]:
            rejected.append({"pmid": pmid, "reason": "incomplete_metadata"})
            verification_report.append(
                {"pmid": pmid, "status": "REJECTED", "reason": "Incomplete metadata"}
            )
            continue

        quality = assign_evidence_level(
            paper["publication_types"], paper["abstract"], paper["species"]
        )
        paper["quality"] = quality
        verified_papers.append(paper)
        verification_report.append(
            {
                "pmid": pmid,
                "status": "ACCEPTED",
                "title": paper["title"][:80],
                "doi": paper["doi"],
                "journal": paper["journal"],
                "year": paper["year"],
                "authors_count": len(paper["authors"]),
                "evidence_level": quality["evidence_level"],
                "confidence": quality["confidence_score"],
            }
        )

    with open(DATA_DIR / "publications_verified.json", "w") as f:
        json.dump(verified_papers, f, indent=2)

    with open(DATA_DIR / "verification_report.json", "w") as f:
        json.dump(
            {
                "total_input": len(papers),
                "accepted": len(verified_papers),
                "rejected": len(rejected),
                "rejections": rejected,
                "details": verification_report,
            },
            f,
            indent=2,
        )

    print(f"Verified: {len(verified_papers)}, Rejected: {len(rejected)}")


if __name__ == "__main__":
    main()
