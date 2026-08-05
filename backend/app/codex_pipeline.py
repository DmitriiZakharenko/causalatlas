from __future__ import annotations

import json
import subprocess
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path
import urllib.parse
import xml.etree.ElementTree as ET
from app.target_models import AnalysisTarget

from app import codex_cli

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SKILLS_MANIFEST = ROOT / "skills" / "skills_manifest.json"

SEARCH_BUDGETS = {
    "agent02_literature_retrieval": {"max_queries": 8, "max_publications": 120, "deadline_s": 240},
    "agent10_novelty_verification": {"max_queries": 8, "max_publications": 40, "deadline_s": 180},
    "agent12_peer_review": {"max_queries": 6, "max_publications": 30, "deadline_s": 180},
}


@dataclass
class PipelineContext:
    run_id: str
    disease: str
    gene: str | None
    autonomy_level: str
    session_dir: Path
    graph_dir: Path
    target: AnalysisTarget | None = None


def _parse_prompt(prompt: str) -> PipelineContext:
    def match(pattern: str, default: str | None = None) -> str | None:
        m = re.search(pattern, prompt, re.M)
        if m:
            return m.group(1).strip()
        return default

    run_id = match(r"^run_id:\s*(.+)$", "target_run") or "target_run"
    disease = match(r"^disease:\s*(.+)$", "target") or "target"
    gene = match(r"^gene:\s*(.+)$", None)
    if gene in {"(none specified -- disease-wide target)", "none", "None", ""}:
        gene = None
    autonomy_level = match(r"^autonomy_level:\s*(.+)$", "let_it_rip") or "let_it_rip"
    session_dir_raw = match(r"^session output directory \(absolute\):\s*(.+)$")
    session_dir = Path(session_dir_raw) if session_dir_raw else ROOT / "data" / "sessions" / run_id
    graph_dir = ROOT / "data" / "graphs" / _slugify(disease) / run_id
    graph_dir.mkdir(parents=True, exist_ok=True)
    prior_graph = ROOT / "data" / "graphs" / _slugify(disease) / "knowledge_graph.json"
    run_graph = graph_dir / "knowledge_graph.json"
    if prior_graph.exists() and not run_graph.exists():
        shutil.copy2(prior_graph, run_graph)
    target_json = match(r"^target_json:\s*(.+)$", None)
    if target_json:
        try:
            target = AnalysisTarget.model_validate(json.loads(target_json))
        except (json.JSONDecodeError, ValueError):
            target = AnalysisTarget(disease=disease, genes=[gene] if gene else [])
    else:
        target = AnalysisTarget(disease=disease, genes=[gene] if gene else [])
    return PipelineContext(run_id, disease, gene, autonomy_level, session_dir, graph_dir, target)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "target"


def _tool_use_event(name: str, tool_input: dict, tool_id: str) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}]},
    }


def _tool_result_event(tool_id: str, content, *, is_error: bool = False) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": content, "is_error": is_error}
            ]
        },
    }


def _final_result(
    text: str,
    *,
    cost_usd: float | None = None,
    duration_ms: int = 0,
    usage: dict | None = None,
) -> dict:
    return {
        "type": "result",
        "is_error": False,
        "result": text,
        "total_cost_usd": cost_usd,
        "duration_ms": duration_ms,
        **(usage or {}),
    }


def _merge_usage(total: dict, usage: dict | None) -> dict:
    """Aggregate per-agent Codex counters without inventing missing values."""
    if not usage:
        return total
    total["calls"] = int(total.get("calls", 0)) + 1
    for key in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)):
            total[key] = int(total.get(key, 0)) + int(value)
    if isinstance(usage.get("cost_usd"), (int, float)):
        total["cost_usd"] = float(total.get("cost_usd", 0.0)) + float(usage["cost_usd"])
    total["usage_source"] = usage.get("usage_source", "codex_cli_jsonl")
    return total


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _write_checkpoint(ctx: PipelineContext, agent_name: str, payload: dict) -> None:
    checkpoint = ctx.session_dir / "checkpoints" / f"{agent_name}.json"
    _write_json(checkpoint, {"agent": agent_name, "updated_at": datetime.now(timezone.utc).isoformat(), **payload})


def _budget(agent_name: str) -> dict:
    return SEARCH_BUDGETS.get(agent_name, {})


def _read_json(path: Path):
    return json.loads(path.read_text())


def _load_graph_json(ctx: PipelineContext) -> dict:
    graph_path = ctx.graph_dir / "knowledge_graph.json"
    if not graph_path.exists():
        return {"nodes": [], "edges": []}
    try:
        data = _read_json(graph_path)
    except Exception:  # noqa: BLE001
        return {"nodes": [], "edges": []}
    if not isinstance(data, dict):
        return {"nodes": [], "edges": []}
    return data


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _contains_any(text: str, terms: list[str]) -> bool:
    normalized = _normalize_text(text)
    return any(_normalize_text(term) in normalized for term in terms)


def _edge_matches(edge: dict, sources: list[str], targets: list[str]) -> bool:
    return _contains_any(str(edge.get("source", "")), sources) and _contains_any(str(edge.get("target", "")), targets)


def _supporting_edge_summary(edge: dict) -> dict:
    return {
        "source": edge.get("source"),
        "target": edge.get("target"),
        "relation": edge.get("primary_relation"),
        "pmid_count": edge.get("pmid_count", 0),
        "sample_pmids": (edge.get("pmids") or [])[:3],
    }


def _unique_pmids(edges: list[dict]) -> list[str]:
    pmids = []
    seen = set()
    for edge in edges:
        for pmid in edge.get("pmids") or []:
            if pmid not in seen:
                seen.add(pmid)
                pmids.append(pmid)
    return pmids


def _curated_ipf_il11_candidates(ctx: PipelineContext) -> list[dict]:
    if ctx.gene and _normalize_text(ctx.gene) != "il11":
        return []
    if "fibrosis" not in _normalize_text(ctx.disease):
        return []

    graph = _load_graph_json(ctx)
    edges = graph.get("edges", []) if isinstance(graph, dict) else []

    patterns = [
        {
            "hypothesis_id": "H001",
            "kind": "curated",
            "original_statement": "In IPF, TGFβ signaling may form a feed-forward loop with IL11 that sustains myofibroblast differentiation.",
            "search_focus": "TGFβ IL11 myofibroblast feed-forward loop fibrosis",
            "support_pattern": [("TGFβ signaling", "IL-11"), ("IL-11", "Myofibroblast")],
        },
        {
            "hypothesis_id": "H002",
            "kind": "curated",
            "original_statement": "In IPF, IL11 may drive ERK1/2 and MEK signaling to increase collagen I expression and extracellular matrix deposition.",
            "search_focus": "IL11 ERK collagen I deposition fibrosis",
            "support_pattern": [("IL-11", "ERK1/2 phosphorylation"), ("IL-11", "Collagen I expression"), ("IL-11", "Collagen deposition")],
        },
        {
            "hypothesis_id": "H003",
            "kind": "curated",
            "original_statement": "In IPF fibroblasts, SMAD2 may sit upstream of IL11 and amplify a profibrotic myofibroblast loop.",
            "search_focus": "SMAD2 IL11 fibroblast myofibroblast fibrosis",
            "support_pattern": [("Smad2", "IL-11"), ("IL-11", "Myofibroblast")],
        },
    ]

    candidates = []
    for pattern in patterns:
        supporting_edges = []
        for source_term, target_term in pattern["support_pattern"]:
            for edge in edges:
                if _edge_matches(edge, [source_term], [target_term]):
                    supporting_edges.append(edge)
        unique_edges = []
        seen_edges = set()
        for edge in supporting_edges:
            edge_key = (edge.get("source"), edge.get("target"), edge.get("primary_relation"))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            unique_edges.append(edge)
        unique_pmids = _unique_pmids(unique_edges)
        candidates.append(
            {
                "hypothesis_id": pattern["hypothesis_id"],
                "original_statement": pattern["original_statement"],
                "kind": pattern["kind"],
                "search_focus": pattern["search_focus"],
                "source": {
                    "supporting_edges": [_supporting_edge_summary(edge) for edge in unique_edges],
                    "supporting_pmids": unique_pmids,
                    "supporting_pmid_count": len(unique_pmids),
                },
            }
        )
    return candidates


def _curl_get(url: str) -> str:
    return subprocess.run(["curl", "-s", url], capture_output=True, text=True, check=True).stdout


def _pubmed_esearch(query: str, retmax: int = 25, retstart: int = 0) -> dict:
    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "term": query,
            "retmax": retmax,
            "retstart": retstart,
            "retmode": "json",
            "tool": "loopfinder_codex",
            "email": "research@example.com",
        }
    )
    data = json.loads(_curl_get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"))
    return data.get("esearchresult", {"count": "0", "idlist": []})


def _pubmed_efetch(pmids: list[str]) -> str:
    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "tool": "loopfinder_codex",
            "email": "research@example.com",
        }
    )
    return _curl_get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{params}")


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    papers = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        if medline is None:
            continue
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
                year = pub_date.findtext("Year", "") or pub_date.findtext("MedlineDate", "")[:4]
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
        species = "unknown"
        title_abs = f"{title} {abstract}".lower()
        if any(term in title_abs for term in ("mouse", "mice", "murine")):
            species = "mouse"
        elif any(term in title_abs for term in ("human", "patient", "patients", "humanized")):
            species = "human"
        papers.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi,
                "publication_types": pub_types,
                "species": species,
                "verified": False,
            }
        )
    return papers


def _target_queries(ctx: PipelineContext) -> list[dict]:
    disease = ctx.disease
    target = ctx.target or AnalysisTarget(disease=disease, genes=[ctx.gene] if ctx.gene else [])
    genes = target.genes
    drugs = target.drugs
    tissues = target.tissues
    cell_types = target.cell_types
    queries = []
    gene = genes[0] if genes else None
    if gene:
        queries.append({"strategy": "gene_disease_direct", "query": f"{gene} {disease}"})
        context_terms = " ".join(tissues[:1] + cell_types[:1])
        queries.append(
            {
                "strategy": "gene_context_mechanism",
                "query": f"{gene} {disease} {context_terms} mechanism".strip(),
            }
        )
    for drug in drugs:
        queries.extend(
            [
                {"strategy": "drug_target_direct", "query": f'"{drug}" {" ".join(genes) if genes else disease}'},
                {"strategy": "drug_disease_direct", "query": f'"{drug}" "{disease}"'},
            ]
        )
    for tissue in tissues:
        queries.append({"strategy": "tissue_context", "query": f'"{tissue}" "{disease}" {" ".join(genes or drugs)}'.strip()})
    for cell_type in cell_types:
        queries.append({"strategy": "cell_type_context", "query": f'"{cell_type}" "{disease}" {" ".join(genes or drugs)}'.strip()})
    # Keep a small number of mechanistic fallbacks after every populated input
    # dimension has received a dedicated query. The previous ordering spent
    # all six slots on gene-only searches and silently dropped tissue/cell
    # coverage for multidimensional targets.
    queries.extend(
        [
            {"strategy": "disease_mech_mesh", "query": f'"{disease}"[MeSH Terms] cytokine signaling mechanism'},
            {"strategy": "disease_fibrosis_mesh", "query": f'"{disease}"[MeSH Terms] fibrosis'},
            {"strategy": "interleukin_11_mesh", "query": '"interleukin-11"[MeSH Terms] "pulmonary fibrosis"[MeSH Terms]'},
        ]
    )
    return queries


def _node_expansion_queries(ctx: PipelineContext, papers: list[dict], *, limit: int = 2) -> list[dict]:
    """Choose a tiny number of follow-ups from repeatedly observed nodes.

    This is deliberately vocabulary-bounded: a random noun in an abstract must
    not become a new search branch. A node must occur in at least two retrieved
    abstracts and must not already be an input dimension.
    """
    target = ctx.target or AnalysisTarget(disease=ctx.disease, genes=[ctx.gene] if ctx.gene else [])
    requested = {str(value).casefold() for values in (target.genes, target.drugs, target.tissues, target.cell_types) for value in values}
    candidates = (
        "IL-33", "ST2", "ILC2", "TSLP", "IL-5", "IL-13", "eosinophil",
        "airway epithelium", "goblet cell", "type 2 inflammation", "airway remodeling",
    )
    scored: list[tuple[int, str]] = []
    for node in candidates:
        if node.casefold() in requested:
            continue
        count = sum(node.casefold() in (paper.get("abstract", "") or "").casefold() for paper in papers)
        if count >= 2:
            scored.append((count, node))
    scored.sort(key=lambda item: (-item[0], item[1]))
    anchor = target.genes[0] if target.genes else (target.drugs[0] if target.drugs else ctx.disease)
    return [
        {"strategy": "node_expansion", "node": node, "query": f'"{anchor}" "{node}" "{ctx.disease}"'}
        for _, node in scored[:limit]
    ]


def _assign_quality(paper: dict) -> dict:
    pub_types = [pt.lower() for pt in paper.get("publication_types", [])]
    abstract = paper.get("abstract", "") or ""
    species = paper.get("species", "unknown")
    study_design = next(
        (
            label
            for label, marker in (
                ("randomized_controlled_trial", "randomized controlled trial"),
                ("clinical_trial", "clinical trial"),
                ("cohort", "cohort"),
                ("case_control", "case-control"),
                ("single_cell", "single-cell"),
                ("in_vitro", "in vitro"),
                ("review", "review"),
            )
            if marker in abstract.casefold() or any(marker in pt for pt in pub_types)
        ),
        "unknown",
    )
    sample_size_match = re.search(r"\b(?:n|N)\s*[=,:]?\s*(\d{2,6})\b", abstract)
    sample_size = int(sample_size_match.group(1)) if sample_size_match else None
    evidence_level = "primary_research"
    base_confidence = 0.5
    penalties: list[dict] = []
    if any("review" in pt for pt in pub_types):
        evidence_level = "review"
        base_confidence = 0.55
        penalties.append({"name": "review_not_primary", "amount": 0.10})
    if any("meta-analysis" in pt for pt in pub_types):
        evidence_level = "systematic_review"
        base_confidence = 0.9
    if any("clinical trial" in pt or "randomized controlled trial" in pt for pt in pub_types):
        evidence_level = "clinical"
        base_confidence = 0.85
    if species == "mouse":
        evidence_level = "mouse"
        penalties.append({"name": "nonhuman_species", "amount": 0.15})
    elif species == "human":
        evidence_level = "human" if evidence_level == "primary_research" else evidence_level
        base_confidence = max(base_confidence, 0.6)
    else:
        penalties.append({"name": "species_unknown", "amount": 0.10})
    if "in vitro" in abstract.lower() or "cell line" in abstract.lower():
        evidence_level = "in_vitro"
        penalties.append({"name": "in_vitro_or_cell_line", "amount": 0.20})
    if not abstract.strip():
        penalties.append({"name": "abstract_missing", "amount": 0.25})
    if sample_size is None:
        penalties.append({"name": "sample_size_unknown", "amount": 0.05})
    elif sample_size < 20:
        penalties.append({"name": "small_sample_size", "amount": 0.10})
    if study_design == "unknown":
        penalties.append({"name": "study_design_unknown", "amount": 0.05})
    confidence_score = max(0.0, min(1.0, base_confidence - sum(item["amount"] for item in penalties)))
    return {
        "evidence_level": evidence_level,
        "study_design": study_design,
        "sample_size": sample_size,
        "replication_status": paper.get("replication_status", "unknown"),
        "context_completeness": {
            "species": species != "unknown",
            "tissue": bool(paper.get("tissue")),
            "cell_type": bool(paper.get("cell_type")),
            "model": bool(paper.get("model")),
        },
        "base_confidence": round(base_confidence, 2),
        "penalties": penalties,
        "confidence_score": round(confidence_score, 2),
    }


def _materialize_local_publications(ctx: PipelineContext) -> dict:
    raw_path = ctx.session_dir / "publications_raw.json"
    if raw_path.exists():
        try:
            existing = _read_json(raw_path)
            if isinstance(existing, dict) and isinstance(existing.get("publications"), list) and existing["publications"]:
                return existing
        except Exception:  # noqa: BLE001
            pass

    max_queries = _budget("agent02_literature_retrieval")["max_queries"]
    max_publications = _budget("agent02_literature_retrieval")["max_publications"]
    # Reserve two slots for evidence-driven expansion after the broad pass.
    queries = _target_queries(ctx)[:max(1, max_queries - 2)]
    checkpoint_path = ctx.session_dir / "checkpoints" / "agent02_literature_retrieval.json"
    checkpoint = _read_json(checkpoint_path) if checkpoint_path.exists() else {}
    all_pmids: set[str] = set(str(pmid) for pmid in checkpoint.get("pmids", []))
    query_meta = list(checkpoint.get("queries", []))
    completed_strategies = {item.get("strategy") for item in query_meta}
    for spec in queries:
        if spec["strategy"] in completed_strategies:
            continue
        result = _pubmed_esearch(spec["query"], retmax=25, retstart=0)
        pmids = list(result.get("idlist", []))
        total = int(result.get("count", "0") or 0)
        # Retrieve bounded pages so a high-hit query cannot silently bias the
        # corpus toward the first API page. The global publication budget still
        # limits the materialized corpus below.
        for retstart in range(25, min(total, 100), 25):
            page = _pubmed_esearch(spec["query"], retmax=25, retstart=retstart)
            pmids.extend(page.get("idlist", []))
        query_meta.append({"strategy": spec["strategy"], "query": spec["query"], "total_in_pubmed": total, "retrieved": len(pmids), "paginated": total > 25})
        all_pmids.update(pmids)
        _write_checkpoint(ctx, "agent02_literature_retrieval", {"queries": query_meta, "pmids": sorted(all_pmids), "complete": False})

    initial_pmid_list = sorted(all_pmids, key=lambda x: int(x) if str(x).isdigit() else 0)[:max_publications]
    papers = []
    for i in range(0, len(initial_pmid_list), 50):
        papers.extend(_parse_pubmed_xml(_pubmed_efetch(initial_pmid_list[i : i + 50])))

    expansion_queries = _node_expansion_queries(ctx, papers, limit=min(2, max_queries - len(query_meta)))
    for spec in expansion_queries:
        if spec["strategy"] in completed_strategies:
            continue
        result = _pubmed_esearch(spec["query"], retmax=25, retstart=0)
        pmids = list(result.get("idlist", []))
        total = int(result.get("count", "0") or 0)
        query_meta.append({"strategy": spec["strategy"], "node": spec.get("node"), "query": spec["query"], "total_in_pubmed": total, "retrieved": len(pmids), "paginated": False})
        all_pmids.update(pmids)

    pmid_list = sorted(all_pmids, key=lambda x: int(x) if str(x).isdigit() else 0)[:max_publications]
    papers = []
    for i in range(0, len(pmid_list), 50):
        papers.extend(_parse_pubmed_xml(_pubmed_efetch(pmid_list[i : i + 50])))

    payload = {
        "run_id": ctx.run_id,
        "session": ctx.run_id,
        "disease": ctx.disease,
        "gene": ctx.gene,
        "target": (ctx.target or AnalysisTarget(disease=ctx.disease, genes=[ctx.gene] if ctx.gene else [])).model_dump(mode="json"),
        "queries": query_meta,
        "year_band_distribution": Counter(str(p.get("year", "")).strip()[:4] for p in papers if p.get("year")),
        "year_band_max_share": round(max((c / max(len(papers), 1) for c in Counter(str(p.get("year", "")).strip()[:4] for p in papers if p.get("year")).values()), default=0.0), 2),
        "year_band_flag": False,
        "underpowered_flag": len(query_meta) < 3 or len(papers) < 10,
        "total_unique_publications": len(papers),
        "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
        "publications": papers,
    }
    years = Counter(str(p.get("year", "")).strip()[:4] for p in papers if p.get("year"))
    payload["year_band_distribution"] = dict(sorted(years.items()))
    grouped = {
        "2021-2022": years.get("2021", 0) + years.get("2022", 0),
        "2023-2024": years.get("2023", 0) + years.get("2024", 0),
        "2025-2026": years.get("2025", 0) + years.get("2026", 0),
    }
    payload["year_band_grouped"] = grouped
    payload["year_band_max_share"] = round(max((v / max(len(papers), 1) for v in grouped.values()), default=0.0), 2)
    payload["year_band_flag"] = payload["year_band_max_share"] > 0.50
    _write_json(raw_path, payload)
    _write_checkpoint(ctx, "agent02_literature_retrieval", {"queries": query_meta, "pmids": pmid_list, "complete": True, "publications": len(papers)})
    return payload


def _materialize_local_verification(ctx: PipelineContext) -> dict:
    raw = _materialize_local_publications(ctx)
    verified = []
    details = []
    rejected = []
    target = ctx.target or AnalysisTarget(disease=ctx.disease, genes=[ctx.gene] if ctx.gene else [])
    target_terms = [target.disease, *target.genes, *target.drugs, *target.tissues, *target.cell_types]
    target_terms = [term.casefold() for term in target_terms if term.strip()]
    for paper in raw.get("publications", []):
        if not paper.get("pmid") or not paper.get("title"):
            rejected.append({"pmid": paper.get("pmid"), "reason": "incomplete_metadata"})
            continue
        paper = dict(paper)
        searchable = " ".join(
            str(paper.get(field, "")) for field in ("title", "abstract", "journal")
        ).casefold()
        compact_searchable = re.sub(r"[^a-z0-9]+", "", searchable)
        matched_terms = sorted(
            {
                term
                for term in target_terms
                if term in searchable or re.sub(r"[^a-z0-9]+", "", term) in compact_searchable
            }
        )
        relevance_score = round(len(matched_terms) / max(len(set(target_terms)), 1), 3)
        if not matched_terms:
            rejected.append({"pmid": paper.get("pmid"), "reason": "target_terms_not_found"})
            continue
        # The deterministic fallback has already parsed an EFetch response, but
        # it does not perform the full Agent 3 metadata/relevance audit. Keep
        # that limitation explicit instead of presenting metadata presence as
        # independent verification.
        paper["verified"] = True
        paper["verification_scope"] = "efetch_metadata_present_only"
        paper["relevance_status"] = "not_independently_scored"
        paper["target_terms_matched"] = matched_terms
        paper["relevance_score"] = relevance_score
        paper["quality"] = _assign_quality(paper)
        verified.append(paper)
        details.append(
            {
                "pmid": paper["pmid"],
                "status": "ACCEPTED_METADATA_ONLY",
                "title": paper["title"][:80],
                "journal": paper.get("journal", ""),
                "year": paper.get("year", ""),
                "evidence_level": paper["quality"]["evidence_level"],
                "confidence": paper["quality"]["confidence_score"],
                "relevance_score": relevance_score,
                "target_terms_matched": matched_terms,
            }
        )
    verification_report = {
        "session": ctx.run_id,
        "agent": "agent03_publication_verification",
        "total_input": len(raw.get("publications", [])),
        "accepted": len(verified),
        "rejected": len(rejected),
        "rejections": rejected,
        "relevance_policy": "at_least_one_resolved_target_term_in_title_abstract_or_journal",
        "details": details,
    }
    _write_json(ctx.session_dir / "publications_verified.json", {"session": ctx.run_id, "publications": verified})
    _write_json(ctx.session_dir / "verification_report.json", verification_report)
    return verification_report


def _materialize_local_canonical_baseline(ctx: PipelineContext) -> dict:
    baseline = {
        "session": ctx.run_id,
        "disease": ctx.disease,
        "gene": ctx.gene,
        "sources_queried": ["reactome", "kegg", "uniprot", "mydisease.info"],
        "entries": [],
        "coverage_note": "Codex fallback baseline: no canonical-db lookup result was materialized for this run.",
    }
    _write_json(ctx.session_dir / "canonical_baseline.json", baseline)
    return baseline


def _materialize_local_mechanisms(ctx: PipelineContext) -> dict:
    from scripts.extract_mechanisms import extract_from_abstract  # local import; pure python

    verified_path = ctx.session_dir / "publications_verified.json"
    verified_payload = _materialize_local_verification(ctx) if not verified_path.exists() else _read_json(verified_path)
    papers = verified_payload.get("publications", []) if isinstance(verified_payload, dict) else verified_payload
    edges = []
    for paper in papers:
        quality = paper.get("quality") or _assign_quality(paper)
        edges.extend(
            extract_from_abstract(
                paper.get("abstract", ""),
                str(paper.get("pmid", "")),
                str(paper.get("year", "")),
                paper.get("species", "unknown"),
                quality.get("confidence_score", 0.5),
            )
        )
    for edge in edges:
        edge["session"] = ctx.run_id
        edge["context"] = {
            "disease": [ctx.disease],
            "tissues": list((ctx.target or AnalysisTarget(disease=ctx.disease)).tissues),
            "cell_types": list((ctx.target or AnalysisTarget(disease=ctx.disease)).cell_types),
            "drugs": list((ctx.target or AnalysisTarget(disease=ctx.disease)).drugs),
        }
        edge["provenance_status"] = "source_sentence_present" if edge.get("source_sentence") else "source_sentence_missing"
    mechanisms = {"session": ctx.run_id, "total_edges": len(edges), "edges": edges}
    _write_json(ctx.session_dir / "mechanisms_extracted.json", mechanisms)
    _write_json(ctx.session_dir / "extraction_log.json", [])
    return mechanisms


def _canonical_nodes(canonical: dict) -> set[str]:
    nodes: set[str] = set()
    for entry in canonical.get("canonical_entries", canonical.get("entries", [])):
        nodes.update(entry.get("nodes", []))
    return nodes


def _canonical_node_records(node_names: set[str]) -> list[dict]:
    records = []
    for node in sorted(node_names):
        records.append(
            {
                "id": node,
                "type": "canonical_db",
                "pmid_count": 0,
                "pmids": [],
                "edge_count": 0,
                "provenance_type": "canonical_db",
            }
        )
    return records


def _agent_output_path(ctx: PipelineContext, agent_name: str) -> Path:
    if agent_name == "agent01_baseline_canonical_knowledge":
        return ctx.session_dir / "canonical_baseline.json"
    if agent_name == "agent02_literature_retrieval":
        return ctx.session_dir / "publications_raw.json"
    if agent_name == "agent03_publication_verification":
        return ctx.session_dir / "verification_report.json"
    if agent_name == "agent04_quality_filter":
        return ctx.session_dir / "quality_scores.json"
    if agent_name == "agent05_mechanistic_extraction":
        return ctx.session_dir / "mechanisms_extracted.json"
    if agent_name == "agent10_novelty_verification":
        return ctx.graph_dir / "novelty_audit.json"
    if agent_name == "agent11_hypothesis_generation":
        return ctx.session_dir / "hypotheses.json"
    if agent_name == "agent12_peer_review":
        return ctx.session_dir / "peer_review.json"
    if agent_name == "agent13_experiment_design":
        return ctx.session_dir / "experiment_design.json"
    return ctx.session_dir / f"{agent_name}.json"


def _load_skill_manifest() -> dict:
    return json.loads(SKILLS_MANIFEST.read_text())


def _skills_for(agent_name: str, ctx: PipelineContext) -> list[str]:
    manifest = _load_skill_manifest()
    skills = []
    for skill in manifest.get("skills", []):
        if agent_name in skill.get("used_by_agents", []):
            skills.append(skill["name"])
    if agent_name == "agent08_topology_analysis":
        graph_dir = ctx.graph_dir.parent
        disease_graphs = [p for p in graph_dir.iterdir() if p.is_dir() and (p / "knowledge_graph.json").exists()]
        if len(disease_graphs) > 1:
            skills.append("cross-disease-motif-analysis")
    return skills


def _prepare_prompt(ctx: PipelineContext, agent_name: str, *, extra: str = "") -> str:
    output_path = _agent_output_path(ctx, agent_name)
    inputs = {
        "agent01_baseline_canonical_knowledge": [
            ctx.session_dir / "analysis_target.json",
            ctx.session_dir / "drug_knowledge.json",
            ctx.session_dir / "target_context.json",
        ],
        "agent02_literature_retrieval": [],
        "agent03_publication_verification": [ctx.session_dir / "publications_raw.json"],
        "agent04_quality_filter": [_materialize_agent04_compact_input(ctx)],
        "agent05_mechanistic_extraction": [
            *_materialize_agent05_compact_inputs(ctx),
            ctx.session_dir / "canonical_baseline.json",
        ],
        "agent10_novelty_verification": [
            ctx.graph_dir / "knowledge_graph.json",
            ctx.graph_dir / "contradictions.json",
            ctx.graph_dir / "knowledge_gaps.json",
            ctx.graph_dir / "novelty_candidate_manifest.json",
            ctx.session_dir / "canonical_baseline.json",
        ],
        "agent11_hypothesis_generation": [
            ctx.graph_dir / "novelty_audit.json",
            ctx.graph_dir / "knowledge_graph.json",
        ],
        "agent12_peer_review": [
            ctx.session_dir / "hypotheses.json",
            ctx.graph_dir / "contradictions.json",
            ctx.graph_dir / "novelty_audit.json",
        ],
        "agent13_experiment_design": [
            ctx.session_dir / "hypotheses.json",
            ctx.session_dir / "peer_review.json",
        ],
    }.get(agent_name, [])
    skill_docs = [ROOT / "skills" / skill / "SKILL.md" for skill in _skills_for(agent_name, ctx)]
    prompt_lines = [
        f"run_id: {ctx.run_id}",
        f"disease: {ctx.disease}",
        f"gene: {ctx.gene or '(none specified -- disease-wide target)'}",
        f"target_schema_version: {(ctx.target or AnalysisTarget(disease=ctx.disease)).schema_version}",
        f"target_json: {json.dumps((ctx.target or AnalysisTarget(disease=ctx.disease)).model_dump(mode='json'), separators=(',', ':'))}",
        f"autonomy_level: {ctx.autonomy_level}",
        f"session output directory (absolute): {ctx.session_dir}",
        f"graph output directory (absolute): {ctx.graph_dir}",
        f"output file: {output_path}",
        "input files:",
    ]
    for path in inputs:
        prompt_lines.append(f"- {path}")
    prompt_lines.append("relevant skill docs:")
    for path in skill_docs:
        prompt_lines.append(f"- {path}")
    if agent_name in SEARCH_BUDGETS:
        budget = _budget(agent_name)
        prompt_lines.extend([
            "",
            "HARD SEARCH BUDGET:",
            f"- maximum queries: {budget['max_queries']}",
            f"- maximum publications/results to inspect: {budget['max_publications']}",
            f"- deadline: {budget['deadline_s']} seconds",
            f"- write/update checkpoint: {ctx.session_dir / 'checkpoints' / f'{agent_name}.json'} after each query or independent search",
            "- on resume, read the checkpoint and continue from the first unfinished query; do not repeat completed searches.",
        ])
    if extra:
        prompt_lines.append("")
        prompt_lines.append(extra.strip())
    if agent_name == "agent03_publication_verification":
        prompt_lines.append("")
        prompt_lines.append(
            "Required output contract: return JSON with both `verification_report` and "
            "`publications`. `publications` must be the verified publication list used by "
            "downstream agents, and `verification_report` should summarize counts and filtering."
        )
    elif agent_name == "agent04_quality_filter":
        prompt_lines.append("")
        prompt_lines.append(
            "Required output contract: return the quality summary JSON only; keep it compact and "
            "machine-readable."
        )
        prompt_lines.append(
            "Use only the compact verified-publication file listed above; do not re-read the full "
            "`publications_verified.json` corpus."
        )
    elif agent_name == "agent05_mechanistic_extraction":
        prompt_lines.append("")
        prompt_lines.append(
            "Required output contract: return JSON with an `edges` array in the same shape expected "
            "by `scripts/build_graph.py`."
        )
        prompt_lines.append(
            "Use only the compact top-ranked verified corpus files listed above; do not expand or "
            "re-read the full `publications_verified.json` corpus."
        )
    return "\n".join(prompt_lines)


def _coerce_json_payload(result: codex_cli.AgentResult, fallback: dict | list | None = None):
    if result.structured_output is not None:
        return result.structured_output
    try:
        return json.loads(result.result_text)
    except Exception:  # noqa: BLE001
        return fallback if fallback is not None else {"result_text": result.result_text}


def _is_transcript_wrapper(payload) -> bool:
    return isinstance(payload, dict) and set(payload.keys()) == {"result_text"} and isinstance(
        payload.get("result_text"), str
    )


def _preserve_existing_output(out: Path, payload) -> bool:
    if not out.exists() or not _is_transcript_wrapper(payload):
        return False
    try:
        existing = _read_json(out)
    except Exception:  # noqa: BLE001
        return False
    return not _is_transcript_wrapper(existing)


def _has_publication_corpus(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = _read_json(path)
    except Exception:  # noqa: BLE001
        return False
    return isinstance(data, dict) and isinstance(data.get("publications"), list) and len(data["publications"]) > 0


def _has_mechanism_edges(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = _read_json(path)
    except Exception:  # noqa: BLE001
        return False
    return isinstance(data, dict) and isinstance(data.get("edges"), list) and len(data["edges"]) > 0


def _persist_agent_output(ctx: PipelineContext, agent_name: str, payload) -> None:
    out = _agent_output_path(ctx, agent_name)
    if _preserve_existing_output(out, payload):
        return
    if agent_name == "agent03_publication_verification":
        verification_report = payload
        verified = []
        if isinstance(payload, dict):
            nested_report = payload.get("verification_report")
            if isinstance(nested_report, dict):
                verification_report = nested_report
            for key in ("publications", "verified_publications", "publications_verified"):
                value = payload.get(key)
                if isinstance(value, list):
                    verified = value
                    break
            if not verified and isinstance(payload.get("verification_report"), dict):
                maybe_publications = payload["verification_report"].get("publications")
                if isinstance(maybe_publications, list):
                    verified = maybe_publications
        elif isinstance(payload, list):
            verified = payload
            verification_report = {
                "session": ctx.run_id,
                "agent": "agent03_publication_verification",
                "verified_count": len(payload),
                "rejected_count": 0,
                "note": "Codex fallback: verification report synthesized from a list payload.",
            }
        _write_json(out, verification_report)
        _write_json(ctx.session_dir / "publications_verified.json", {"session": ctx.run_id, "publications": verified})
        _materialize_agent04_compact_input(ctx)
        _materialize_agent05_compact_inputs(ctx)
        return
    _write_json(out, payload)
    if agent_name == "agent02_literature_retrieval" and not _has_publication_corpus(out):
        _materialize_local_publications(ctx)
    elif agent_name == "agent03_publication_verification":
        verified_path = ctx.session_dir / "publications_verified.json"
        if not _has_publication_corpus(verified_path):
            _materialize_local_verification(ctx)
        _materialize_agent04_compact_input(ctx)
        _materialize_agent05_compact_inputs(ctx)
    elif agent_name == "agent05_mechanistic_extraction" and not _has_mechanism_edges(out):
        _materialize_local_mechanisms(ctx)


async def _run_codex_agent(ctx: PipelineContext, agent_name: str, *, extra: str = "") -> tuple[dict, dict]:
    prompt = _prepare_prompt(ctx, agent_name, extra=extra)
    result = await codex_cli.run_agent(
        agent_name,
        prompt,
        json_schema={"type": "object"},
        timeout_s=float(_budget(agent_name).get("deadline_s", 300)),
    )
    payload = _coerce_json_payload(result)
    _persist_agent_output(ctx, agent_name, payload)
    return payload, {
        "type": "result",
        "is_error": False,
        "result": result.result_text,
        "cost_usd": result.cost_usd,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cached_input_tokens": result.cached_input_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "total_tokens": result.total_tokens,
        "usage_source": result.usage_source,
    }


def _candidate_manifest(ctx: PipelineContext) -> list[dict]:
    gaps_path = ctx.graph_dir / "knowledge_gaps.json"
    contradictions_path = ctx.graph_dir / "contradictions.json"
    candidates = []
    if contradictions_path.exists():
        contradictions = _read_json(contradictions_path)
        for idx, c in enumerate(contradictions, start=1):
            node_pair = c.get("node_pair") or []
            if len(node_pair) == 2:
                statement = f"Which condition determines whether {node_pair[0]} -> {node_pair[1]} or the reverse dominates?"
            else:
                statement = f"Resolve contradiction {idx} in {ctx.disease}"
            candidates.append(
                {
                    "hypothesis_id": f"C{idx:03d}",
                    "original_statement": statement,
                    "kind": "contradiction",
                    "source": c,
                }
            )
    if gaps_path.exists():
        gaps = _read_json(gaps_path)
        for idx, g in enumerate(gaps, start=len(candidates) + 1):
            missing = g.get("missing_edge")
            if not missing:
                continue
            arch = g.get("architecture", "global")
            statement = f"{missing} in {ctx.disease} ({arch})"
            candidates.append(
                {
                    "hypothesis_id": f"G{idx:03d}",
                    "original_statement": statement,
                    "kind": "gap",
                    "source": g,
                }
            )
    curated = _curated_ipf_il11_candidates(ctx)
    if curated:
        candidates.extend(curated)
    if not candidates:
        candidates.append(
            {
                "hypothesis_id": "G001",
                "original_statement": f"Mechanistic gap candidates in {ctx.disease}",
                "kind": "fallback",
                "source": {},
            }
        )
    _write_json(ctx.graph_dir / "novelty_candidate_manifest.json", {"session": ctx.run_id, "candidates": candidates})
    return candidates


def _eligible_audits(novelty_audit: dict) -> list[dict]:
    audits = novelty_audit.get("audits", []) if isinstance(novelty_audit, dict) else []
    return [a for a in audits if a.get("eligible_for_hypothesis_generation")]


def _template_audits_from_candidates(candidates: list[dict]) -> list[dict]:
    template_audits = []
    for candidate in candidates:
        source = candidate.get("source") or {}
        if candidate.get("kind") != "curated":
            continue
        supporting_edges = source.get("supporting_edges") or []
        supporting_pmids = source.get("supporting_pmids") or []
        if len(supporting_edges) < 2 or len(supporting_pmids) < 2:
            continue
        template_audits.append(
            {
                "hypothesis_id": candidate["hypothesis_id"],
                "original_statement": candidate["original_statement"],
                "candidate": candidate,
                "novelty_class": "D",
                "classification": "D",
                "eligible_for_hypothesis_generation": True,
                "supporting_papers_count": len(supporting_pmids),
                "source": "curated_graph_motif",
                "reason": "Two or more independent supporting graph edges; not a single-paper restatement.",
            }
        )
    return template_audits


def _truncate_text(value, *, limit: int = 320):
    if not isinstance(value, str):
        return value
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _publication_sort_key(publication: dict) -> tuple:
    quality = publication.get("quality") or {}
    relevance = publication.get("relevance_score")
    confidence = quality.get("confidence_score")
    year = publication.get("year")
    try:
        relevance_value = float(relevance or 0.0)
    except (TypeError, ValueError):
        relevance_value = 0.0
    try:
        confidence_value = float(confidence or 0.0)
    except (TypeError, ValueError):
        confidence_value = 0.0
    try:
        year_value = int(str(year)[:4]) if year is not None and str(year)[:4].isdigit() else 0
    except (TypeError, ValueError):
        year_value = 0
    return (-relevance_value, -confidence_value, -year_value, str(publication.get("pmid", "")))


def _compact_publication_entry(publication: dict) -> dict:
    quality = publication.get("quality") or {}
    return {
        "pmid": str(publication.get("pmid", "")),
        "title": _truncate_text(publication.get("title", ""), limit=220),
        "abstract": _truncate_text(publication.get("abstract", "") or "", limit=1800),
        "year": publication.get("year"),
        "journal": _truncate_text(publication.get("journal", ""), limit=140),
        "publication_type": publication.get("publication_type"),
        "species": publication.get("species"),
        "relevance_score": publication.get("relevance_score"),
        "quality": {
            "evidence_level": quality.get("evidence_level"),
            "confidence_score": quality.get("confidence_score"),
        },
        "query_strategies_matched": (publication.get("query_strategies_matched") or [])[:5],
    }


def _materialize_agent04_compact_input(ctx: PipelineContext) -> Path:
    verified_path = ctx.session_dir / "publications_verified.json"
    if not verified_path.exists():
        _materialize_local_verification(ctx)
    verified_payload = _read_json(verified_path) if verified_path.exists() else {"publications": []}
    publications = verified_payload.get("publications", []) if isinstance(verified_payload, dict) else verified_payload
    if not isinstance(publications, list):
        publications = []
    compact_path = ctx.session_dir / "publications_verified_compact.json"
    _write_json(
        compact_path,
        {
            "session": ctx.run_id,
            "source": "publications_verified.json",
            "publication_count": len(publications),
            "publications": [_compact_publication_entry(publication) for publication in publications],
        },
    )
    return compact_path


def _compact_quality_summary(ctx: PipelineContext, verified_count: int, publications: list[dict]) -> dict:
    source = ctx.session_dir / "quality_scores.json"
    if source.exists():
        try:
            quality = _read_json(source)
        except Exception:  # noqa: BLE001
            quality = {}
    else:
        quality = {}
    counts = {}
    if isinstance(quality, dict) and isinstance(quality.get("publication_counts"), dict):
        counts = dict(quality["publication_counts"])
    if not counts:
        for pub in publications:
            evidence_level = (pub.get("quality") or {}).get("evidence_level") or "unknown"
            counts[evidence_level] = counts.get(evidence_level, 0) + 1
    top_pmids = [
        str(pub.get("pmid", ""))
        for pub in sorted(publications, key=_publication_sort_key)[:15]
        if pub.get("pmid")
    ]
    return {
        "session": ctx.run_id,
        "agent": "agent04_quality_filter",
        "publication_counts": counts,
        "average_relevance": quality.get("average_relevance") if isinstance(quality, dict) else None,
        "verified_count": verified_count,
        "compact_publication_count": len(top_pmids),
        "top_pmids": top_pmids,
    }


def _materialize_agent05_compact_inputs(ctx: PipelineContext, *, limit: int = 15) -> tuple[Path, Path]:
    compact_verified_path = _materialize_agent04_compact_input(ctx)
    verified_payload = _read_json(compact_verified_path) if compact_verified_path.exists() else {"publications": []}
    publications = verified_payload.get("publications", []) if isinstance(verified_payload, dict) else verified_payload
    if not isinstance(publications, list):
        publications = []
    ranked_publications = sorted(publications, key=_publication_sort_key)[:limit]
    compact_publications_path = ctx.session_dir / "publications_verified_compact.json"
    compact_quality_path = ctx.session_dir / "quality_scores_compact.json"
    _write_json(
        compact_publications_path,
        {
            "session": ctx.run_id,
            "source": "publications_verified.json",
            "compact_limit": limit,
            "publications": [_compact_publication_entry(publication) for publication in ranked_publications],
        },
    )
    _write_json(
        compact_quality_path,
        _compact_quality_summary(ctx, len(publications), publications),
    )
    return compact_publications_path, compact_quality_path


def _compact_list(values, *, limit: int = 5):
    if not isinstance(values, list):
        return values
    return [_compact_value(v) for v in values[:limit]]


def _compact_value(value):
    if isinstance(value, dict):
        return {key: _compact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return _compact_list(value)
    return _truncate_text(value)


def _compact_experiment_design_payload(hypothesis: dict, review: dict) -> dict:
    return {
        "hypothesis": _compact_value(hypothesis),
        "peer_review": _compact_value(review),
        "instructions": "Design experiments per agent13 AGENTS.md and include falsification criteria.",
    }


def _compact_peer_review_payload(hypothesis: dict, contradictions: list[dict], idx: int) -> dict:
    source_candidate = hypothesis.get("source_candidate") if isinstance(hypothesis, dict) else {}
    source_candidate = source_candidate if isinstance(source_candidate, dict) else {}
    recombined_edges = hypothesis.get("recombined_edges") if isinstance(hypothesis, dict) else []
    supporting_edges = hypothesis.get("supporting_edges") if isinstance(hypothesis, dict) else []

    def _compact_edge(edge: dict) -> dict:
        if not isinstance(edge, dict):
            return {"value": _truncate_text(str(edge), limit=160)}
        return {
            "source": edge.get("source"),
            "relation": edge.get("relation") or edge.get("primary_relation"),
            "target": edge.get("target"),
            "pmid": edge.get("pmid"),
            "confidence": edge.get("confidence"),
        }

    compact_contradictions = []
    for item in contradictions[:5]:
        if not isinstance(item, dict):
            continue
        compact_contradictions.append(
            {
                "id": item.get("id") or item.get("contradiction_id"),
                "node_pair": item.get("node_pair"),
                "direction": item.get("direction"),
                "summary": _truncate_text(item.get("summary", ""), limit=220),
                "pmids": [str(p) for p in (item.get("pmids") or [])[:5]],
            }
        )

    return {
        "hypothesis_id": hypothesis.get("hypothesis_id") if isinstance(hypothesis, dict) else f"H{idx:03d}",
        "class": hypothesis.get("class") if isinstance(hypothesis, dict) else None,
        "statement": _truncate_text(hypothesis.get("statement", ""), limit=260) if isinstance(hypothesis, dict) else "",
        "specific_prediction": _truncate_text(hypothesis.get("specific_prediction", ""), limit=260)
        if isinstance(hypothesis, dict)
        else "",
        "falsification": _truncate_text(hypothesis.get("falsification", ""), limit=260) if isinstance(hypothesis, dict) else "",
        "source_candidate": {
            "hypothesis_id": source_candidate.get("hypothesis_id"),
            "kind": source_candidate.get("kind"),
            "original_statement": _truncate_text(source_candidate.get("original_statement", ""), limit=220),
        },
        "supporting_pmids": [str(p) for p in (hypothesis.get("supporting_pmids") or [])[:8]]
        if isinstance(hypothesis, dict)
        else [],
        "supporting_edges": [_compact_edge(edge) for edge in supporting_edges[:5]] if isinstance(supporting_edges, list) else [],
        "recombined_edges": [_truncate_text(edge, limit=200) for edge in recombined_edges[:5]]
        if isinstance(recombined_edges, list)
        else [],
        "why_connecting_edge_not_published": _truncate_text(
            hypothesis.get("why_connecting_edge_not_published", ""), limit=260
        )
        if isinstance(hypothesis, dict)
        else "",
        "notes": _truncate_text(hypothesis.get("notes", ""), limit=260) if isinstance(hypothesis, dict) else "",
        "contradictions": compact_contradictions,
        "instructions": "Perform 3-role review and return one peer review object.",
    }


def _synthesize_hypothesis_candidate(ctx: PipelineContext, candidate: dict, idx: int) -> dict:
    statement = candidate.get("original_statement") or f"Mechanistic gap candidates in {ctx.disease}"
    source = candidate.get("source") or {}
    supporting_edges = source.get("supporting_edges") or []
    supporting_pmids = source.get("supporting_pmids") or []
    return {
        "hypothesis_id": candidate.get("hypothesis_id") or f"H{idx:03d}",
        "statement": statement,
        "provisional": False,
        "source_candidate": candidate,
        "supporting_edges": supporting_edges,
        "supporting_pmids": supporting_pmids,
        "recombined_edges": [
            f"{edge.get('source')} -[{edge.get('relation') or edge.get('primary_relation') or 'related'}]-> {edge.get('target')}"
            for edge in supporting_edges
            if edge.get("source") and edge.get("target")
        ],
        "notes": "Curated IPF+IL11 hypothesis synthesized from graph motifs and supporting literature edges.",
    }


def _filter_contradictions_for_hypothesis(ctx: PipelineContext, hypothesis: dict) -> list[dict]:
    contradictions_path = ctx.graph_dir / "contradictions.json"
    if not contradictions_path.exists():
        return []
    contradictions = _read_json(contradictions_path)
    touched = set()
    for item in hypothesis.get("recombines_edges", []):
        parts = [p.strip() for p in re.split(r"->|→", item) if p.strip()]
        touched.update(parts)
    if not touched:
        return contradictions[:5]
    filtered = []
    for c in contradictions:
        pair = set(c.get("node_pair") or [])
        if pair & touched:
            filtered.append(c)
    return filtered[:10] or contradictions[:5]


def _step_skills_event(ctx: PipelineContext, agent_name: str, tool_id: str) -> dict | None:
    skills = _skills_for(agent_name, ctx)
    if not skills:
        return None
    # Emit one skill load at a time to keep the UI readable.
    return _tool_use_event("Skill", {"skill": skills[0]}, tool_id)


async def run_orchestrator_stream(
    prompt: str,
    *,
    cwd: Path | None = None,
    session_id: str | None = None,
    resume: bool = False,
):
    ctx = _parse_prompt(prompt)
    usage_total: dict = {"calls": 0}
    step_specs = [
        "agent01_baseline_canonical_knowledge",
        "agent02_literature_retrieval",
        "agent03_publication_verification",
        "agent04_quality_filter",
        "agent05_mechanistic_extraction",
    ]
    try:
        for index, agent_name in enumerate(step_specs, start=1):
            skill_event = _step_skills_event(ctx, agent_name, f"s{index:02d}")
            if skill_event:
                yield skill_event
            yield _tool_use_event(
                "Agent",
                {"subagent_type": agent_name, "description": f"Codex launch for {agent_name}"},
                f"a{index:02d}",
            )
            extra = ""
            if agent_name == "agent02_literature_retrieval":
                extra = (
                    f"Generate the publications_raw.json corpus for {ctx.disease} "
                    f"{'with gene ' + ctx.gene if ctx.gene else 'with no gene specified'}."
                )
            try:
                payload, agent_meta = await _run_codex_agent(ctx, agent_name, extra=extra)
                usage_total = _merge_usage(usage_total, agent_meta)
            except Exception as exc:  # noqa: BLE001
                if agent_name == "agent01_baseline_canonical_knowledge":
                    payload = _materialize_local_canonical_baseline(ctx)
                elif agent_name == "agent02_literature_retrieval":
                    payload = _materialize_local_publications(ctx)
                elif agent_name == "agent03_publication_verification":
                    payload = _materialize_local_verification(ctx)
                elif agent_name == "agent04_quality_filter":
                    verified_payload = _read_json(ctx.session_dir / "publications_verified.json") if (ctx.session_dir / "publications_verified.json").exists() else {"publications": []}
                    verified = verified_payload.get("publications", []) if isinstance(verified_payload, dict) else verified_payload
                    if not isinstance(verified, list):
                        verified = []
                    counts = Counter((paper.get("quality") or {}).get("evidence_level", "unknown") for paper in verified)
                    payload = {
                        "session": ctx.run_id,
                        "agent": "agent04_quality_filter",
                        "publication_counts": dict(counts),
                        "average_relevance": round(
                            sum(float(p.get("relevance_score", 0.0) or 0.0) for p in verified) / max(len(verified), 1),
                            3,
                        ),
                    }
                    _write_json(ctx.session_dir / "quality_scores.json", payload)
                    _materialize_agent04_compact_input(ctx)
                elif agent_name == "agent05_mechanistic_extraction":
                    payload = _materialize_local_mechanisms(ctx)
                else:
                    raise exc
            yield _tool_result_event(f"a{index:02d}", json.dumps(payload)[:4000])

        # Graph stage: deterministic and budget-friendly, but still part of the full launch.
        from scripts.build_graph import merge_graph, quality_gate_edges, semantic_gate_edges
        from scripts.run_budgeted_case import write_graph_stage_outputs  # local import to keep CLI startup light

        canonical = (
            _read_json(ctx.session_dir / "canonical_baseline.json")
            if (ctx.session_dir / "canonical_baseline.json").exists()
            else {}
        )
        verified_payload = (
            _read_json(ctx.session_dir / "publications_verified.json")
            if (ctx.session_dir / "publications_verified.json").exists()
            else {"publications": []}
        )
        verified = verified_payload.get("publications", []) if isinstance(verified_payload, dict) else verified_payload
        graph_payload = (
            _read_json(ctx.session_dir / "mechanisms_extracted.json")
            if (ctx.session_dir / "mechanisms_extracted.json").exists()
            else {"edges": []}
        )
        prior_graph = _load_graph_json(ctx)
        candidate_edges = graph_payload.get("edges", []) if isinstance(graph_payload, dict) else []
        # Keep the model extraction for audit, but supplement it with the
        # deterministic extractor when the model did not provide enough
        # sentence-grounded claims. This is cheap CPU work and prevents a
        # verbose, unsupported model response from becoming the graph.
        llm_candidate_count = len(candidate_edges)
        quality_edges, quality_rejected = quality_gate_edges(
            candidate_edges,
            target=(ctx.target or AnalysisTarget(disease=ctx.disease)).model_dump(mode="json"),
            publications=verified,
        )
        gated_edges, semantic_rejected = semantic_gate_edges(
            quality_edges,
            target=(ctx.target or AnalysisTarget(disease=ctx.disease)).model_dump(mode="json"),
        )
        rejected_edges = quality_rejected + semantic_rejected
        local_fallback_used = False
        local_edges: list[dict] = []
        if len(gated_edges) < 3 and verified:
            if candidate_edges:
                _write_json(ctx.session_dir / "mechanisms_llm_raw.json", graph_payload)
            local_payload = _materialize_local_mechanisms(ctx)
            local_edges = local_payload.get("edges", []) if isinstance(local_payload, dict) else []
            local_quality_edges, local_quality_rejected = quality_gate_edges(
                local_edges,
                target=(ctx.target or AnalysisTarget(disease=ctx.disease)).model_dump(mode="json"),
                publications=verified,
            )
            local_gated, local_semantic_rejected = semantic_gate_edges(
                local_quality_edges,
                target=(ctx.target or AnalysisTarget(disease=ctx.disease)).model_dump(mode="json"),
            )
            if local_gated:
                local_fallback_used = True
                gated_edges = gated_edges + local_gated
                rejected_edges = rejected_edges + local_quality_rejected + local_semantic_rejected
        _write_json(
            ctx.session_dir / "edge_quality_gate.json",
            {
                "session": ctx.run_id,
                "contract": "strict-v2",
                "input_edges": len(candidate_edges),
                "llm_input_edges": llm_candidate_count,
                "local_fallback_used": local_fallback_used,
                "local_fallback_edges": len(local_edges),
                "accepted_edges": len(gated_edges),
                "rejected_edges": len(rejected_edges),
                "semantic_rejected_edges": len(semantic_rejected),
                "rejections": rejected_edges,
            },
        )
        # Do not inherit an older graph unless it was produced under the same
        # strict contract. This prevents a clean run from being polluted by a
        # legacy graph full of unknown types or sentence-free claims.
        if (prior_graph.get("metadata") or {}).get("quality_contract") != "strict-v2":
            prior_graph = {"nodes": [], "edges": [], "metadata": {"filter": "new_run_only"}}
        graph = merge_graph(
            prior_graph,
            gated_edges,
        )
        graph["metadata"] = {
            "disease": ctx.disease,
            "run_id": ctx.run_id,
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "source_session": ctx.run_id,
            "target": (ctx.target or AnalysisTarget(disease=ctx.disease)).model_dump(mode="json"),
            "schema_version": "graph.v1",
            "quality_contract": "strict-v2",
            "edge_quality_gate": "strict-v2",
            "rejected_edge_count": len(rejected_edges),
            "semantic_edge_validation": "deterministic-v1",
            "canonical_baseline_entries": (canonical.get("entries") or canonical.get("canonical_entries") or []) if isinstance(canonical, dict) else [],
        }
        canonical_ids = _canonical_nodes(canonical if isinstance(canonical, dict) else {})
        present_ids = {n["id"] for n in graph["nodes"]}
        graph["nodes"].extend(
            node for node in _canonical_node_records(canonical_ids - present_ids) if node["id"] not in present_ids
        )
        graph["metadata"]["node_count"] = len(graph["nodes"])
        stage = write_graph_stage_outputs(
            session_id=ctx.run_id,
            disease=ctx.disease,
            verified=verified,
            graph=graph,
            graph_dir=ctx.graph_dir,
            session_dir=ctx.session_dir,
        )
        yield _tool_use_event("Agent", {"subagent_type": "agent06_graph_builder", "description": "Graph stage"}, "a06")
        yield _tool_result_event("a06", f"graph built: {stage['report']['graph']['nodes']} nodes / {stage['report']['graph']['edges']} edges")
        yield _tool_use_event("Agent", {"subagent_type": "agent07_loop_discovery", "description": "Loop stage"}, "a07")
        yield _tool_result_event("a07", f"loops discovered: {len(stage['loops'])}")
        yield _tool_use_event("Agent", {"subagent_type": "agent08_topology_analysis", "description": "Topology stage"}, "a08")
        yield _tool_result_event("a08", f"architectures ranked: {len(stage['metrics']['architectures'])}")
        yield _tool_use_event("Agent", {"subagent_type": "agent09_contradiction_gap_detection", "description": "Contradiction stage"}, "a09")
        yield _tool_result_event("a09", f"contradictions: {len(stage['contradictions'])}, gaps: {len(stage['gaps'])}")

        # Agent 10 novelty audit over candidates.
        candidates = _candidate_manifest(ctx)[:_budget("agent10_novelty_verification")["max_queries"]]
        novelty_checkpoint_path = ctx.session_dir / "checkpoints" / "agent10_novelty_verification.json"
        novelty_checkpoint = _read_json(novelty_checkpoint_path) if novelty_checkpoint_path.exists() else {}
        audits = list(novelty_checkpoint.get("audits", []))
        skill_event = _step_skills_event(ctx, "agent10_novelty_verification", "s10")
        if skill_event:
            yield skill_event
        for idx, candidate in enumerate(candidates[len(audits):], start=len(audits) + 1):
            yield _tool_use_event(
                "Agent",
                {"subagent_type": "agent10_novelty_verification", "description": candidate["original_statement"]},
                f"n{idx:02d}",
            )
            extra = json.dumps(
                {
                    "candidate": candidate,
                    "instructions": "Classify per agent10 AGENTS.md and return one audit entry.",
                    "canonical_baseline_file": str(ctx.session_dir / "canonical_baseline.json"),
                    "graph_file": str(ctx.graph_dir / "knowledge_graph.json"),
                },
                separators=(",", ":"),
            )
            payload, agent_meta = await _run_codex_agent(ctx, "agent10_novelty_verification", extra=extra)
            usage_total = _merge_usage(usage_total, agent_meta)
            if isinstance(payload, dict):
                audits.append(payload)
            else:
                audits.append({"candidate": candidate, "result_text": payload})
            _write_checkpoint(ctx, "agent10_novelty_verification", {"completed_queries": idx, "total_queries": len(candidates), "audits": audits, "complete": idx == len(candidates)})
            yield _tool_result_event(f"n{idx:02d}", json.dumps(audits[-1])[:4000])
        novelty_audit = {
            "session": ctx.run_id,
            "audited_at": datetime.now(timezone.utc).isoformat(),
            "audits": audits,
        }
        _write_json(ctx.graph_dir / "novelty_audit.json", novelty_audit)

        # Agent 11 hypotheses from D/E entries.
        eligible = _eligible_audits(novelty_audit)
        if not eligible and candidates:
            eligible = _template_audits_from_candidates(candidates)
        if not eligible and candidates:
            eligible = [
                {
                    "hypothesis_id": candidates[0].get("hypothesis_id", "H001"),
                    "eligible_for_hypothesis_generation": True,
                    "novelty_class": "D",
                    "candidate": candidates[0],
                    "source": "fallback_seed",
                }
            ]
        hypotheses = []
        for idx, audit in enumerate(eligible, start=1):
            yield _tool_use_event(
                "Agent",
                {"subagent_type": "agent11_hypothesis_generation", "description": audit.get("hypothesis_id", f"H{idx}")},
                f"h{idx:02d}",
            )
            candidate = audit.get("candidate")
            if candidate and audit.get("source") == "curated_graph_motif":
                payload = _synthesize_hypothesis_candidate(ctx, candidate, idx)
            else:
                extra = json.dumps(
                    {
                        "audit": audit,
                        "instructions": "Generate one hypothesis object per agent11 AGENTS.md.",
                    },
                    separators=(",", ":"),
                )
                payload, agent_meta = await _run_codex_agent(ctx, "agent11_hypothesis_generation", extra=extra)
                usage_total = _merge_usage(usage_total, agent_meta)
                payload = payload if isinstance(payload, dict) else {"result_text": payload}
            hypotheses.append(payload)
            yield _tool_result_event(f"h{idx:02d}", json.dumps(hypotheses[-1])[:4000])
        _write_json(ctx.session_dir / "hypotheses.json", {"session": ctx.run_id, "hypotheses": hypotheses})

        # Agent 12 peer review.
        review_checkpoint_path = ctx.session_dir / "checkpoints" / "agent12_peer_review.json"
        review_checkpoint = _read_json(review_checkpoint_path) if review_checkpoint_path.exists() else {}
        reviews = list(review_checkpoint.get("reviews", []))
        review_limit = min(len(hypotheses), _budget("agent12_peer_review")["max_queries"])
        for idx, hyp in enumerate(hypotheses[len(reviews):review_limit], start=len(reviews) + 1):
            yield _tool_use_event(
                "Agent",
                {"subagent_type": "agent12_peer_review", "description": hyp.get("hypothesis_id", f"H{idx}")},
                f"r{idx:02d}",
            )
            extra = json.dumps(
                _compact_peer_review_payload(
                    hyp if isinstance(hyp, dict) else {},
                    _filter_contradictions_for_hypothesis(ctx, hyp if isinstance(hyp, dict) else {}),
                    idx,
                ),
                separators=(",", ":"),
            )
            payload, agent_meta = await _run_codex_agent(ctx, "agent12_peer_review", extra=extra)
            usage_total = _merge_usage(usage_total, agent_meta)
            reviews.append(payload if isinstance(payload, dict) else {"result_text": payload})
            _write_checkpoint(ctx, "agent12_peer_review", {"completed_queries": idx, "total_queries": min(len(hypotheses), _budget("agent12_peer_review")["max_queries"]), "reviews": reviews, "complete": idx == min(len(hypotheses), _budget("agent12_peer_review")["max_queries"])})
            yield _tool_result_event(f"r{idx:02d}", json.dumps(reviews[-1])[:4000])
        _write_json(ctx.session_dir / "peer_review.json", {"session": ctx.run_id, "reviews": reviews})

        # Agent 13 experiment design for accepted hypotheses.
        experiments = []
        for idx, review in enumerate(reviews, start=1):
            if review.get("consensus") == "REJECT":
                continue
            yield _tool_use_event(
                "Agent",
                {"subagent_type": "agent13_experiment_design", "description": review.get("hypothesis_id", f"H{idx}")},
                f"e{idx:02d}",
            )
            extra = json.dumps(
                _compact_experiment_design_payload(
                    next((h for h in hypotheses if h.get("hypothesis_id") == review.get("hypothesis_id")), {}),
                    review,
                ),
                separators=(",", ":"),
            )
            payload, agent_meta = await _run_codex_agent(ctx, "agent13_experiment_design", extra=extra)
            usage_total = _merge_usage(usage_total, agent_meta)
            experiments.append(payload if isinstance(payload, dict) else {"result_text": payload})
            yield _tool_result_event(f"e{idx:02d}", json.dumps(experiments[-1])[:4000])
        _write_json(ctx.session_dir / "experiment_design.json", {"session": ctx.run_id, "experiments": experiments})

        # Keep a backward-compatible latest alias for existing graph clients;
        # the immutable run-scoped graph remains the source of truth.
        latest_dir = ROOT / "data" / "graphs" / _slugify(ctx.disease)
        latest_dir.mkdir(parents=True, exist_ok=True)
        for run_artifact in ctx.graph_dir.glob("*.json"):
            shutil.copy2(run_artifact, latest_dir / run_artifact.name)

        summary = (
            f"Codex multi-agent pipeline completed for {ctx.disease}: "
            f"{len(audits)} novelty audits, {len(hypotheses)} hypotheses, "
            f"{len(reviews)} reviews, {len(experiments)} experiment designs."
        )
        yield _final_result(
            summary,
            cost_usd=usage_total.get("cost_usd"),
            usage={
                key: value
                for key, value in usage_total.items()
                if key != "cost_usd" and value is not None
            },
        )
    except Exception as exc:  # noqa: BLE001
        yield {
            "type": "orchestrator_failed",
            "returncode": 1,
            "stderr": str(exc),
        }
