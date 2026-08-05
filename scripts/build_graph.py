#!/usr/bin/env python3
"""
Agents 5-8: Knowledge graph builder, validator, architecture discovery, gap analysis.
"""
import json
import hashlib
from collections import defaultdict
from pathlib import Path
import re

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GRAPH_DIR = Path(__file__).resolve().parent.parent / "graph"


def _unique(values):
    """Return stable, JSON-safe unique values without dropping falsy metadata."""
    result = []
    seen = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        if marker not in seen:
            seen.add(marker)
            result.append(value)
    return result


def _edge_records(edge: dict) -> list[dict]:
    """Expand both current and legacy edges without throwing provenance away."""
    relations = edge.get("relations") or [edge.get("primary_relation") or edge.get("relation") or "related"]
    pmids = list(edge.get("pmids") or ([] if not edge.get("pmid") else [edge["pmid"]]))
    sessions = list(edge.get("sessions") or ([] if not (edge.get("session") or edge.get("run_id")) else [edge.get("session") or edge.get("run_id")]))
    refs = list(edge.get("source_refs") or [])
    if edge.get("source_sentence"):
        refs.append({"pmid": edge.get("pmid", ""), "source_sentence": edge["source_sentence"]})
    records = []
    for relation in relations:
        record = dict(edge)
        record.update({"relation": relation, "pmids": pmids, "sessions": sessions, "source_refs": refs})
        records.append(record)
    return records


def _compact_label(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _entity_mentioned(label: object, text: str) -> bool:
    key = _compact_label(label)
    if not key:
        return False
    compact = _compact_label(text)
    return key in compact


def quality_gate_edges(
    edges: list[dict],
    *,
    target: dict | None = None,
    publications: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Keep only auditable, target-relevant claims for a new graph.

    The graph is intentionally smaller than the raw extraction. A claim must
    have a PMID, a source sentence containing both endpoints, known node types,
    and either a target anchor in its paper or an endpoint matching one of the
    requested dimensions. Rejected claims remain available for audit.
    """
    target = target or {}
    anchors = [
        target.get("disease", ""),
        *(target.get("genes") or []),
        *(target.get("drugs") or []),
        *(target.get("tissues") or []),
        *(target.get("cell_types") or []),
    ]
    known_types = {"Cell", "Cytokine", "Molecule", "Tissue", "Clinical_phenotype", "Pathway", "Gene", "Drug", "Cell_type"}
    paper_map = {str(p.get("pmid")): p for p in (publications or []) if p.get("pmid")}
    accepted: list[dict] = []
    rejected: list[dict] = []
    for edge in edges:
        reasons: list[str] = []
        pmids = [str(p) for p in (edge.get("pmids") or ([] if not edge.get("pmid") else [edge.get("pmid")])) if p]
        sentence = str(edge.get("source_sentence") or "")
        source = edge.get("source")
        dest = edge.get("target")
        if not pmids:
            reasons.append("missing_pmid")
        if not sentence:
            reasons.append("missing_source_sentence")
        elif not (_entity_mentioned(source, sentence) and _entity_mentioned(dest, sentence)):
            reasons.append("endpoints_not_in_source_sentence")
        if edge.get("source_type") not in known_types or edge.get("target_type") not in known_types:
            reasons.append("unknown_node_type")
        provenance_type = edge.get("provenance_type") or ("pmid" if pmids else "unknown")
        if provenance_type != "pmid":
            reasons.append("non_pmid_provenance")
        paper = paper_map.get(pmids[0]) if pmids else None
        paper_text = f"{(paper or {}).get('title', '')} {(paper or {}).get('abstract', '')}"
        paper_anchor = any(_entity_mentioned(anchor, paper_text) for anchor in anchors if anchor)
        endpoint_anchor = any(
            _entity_mentioned(anchor, f"{source} {dest}") for anchor in anchors if anchor
        )
        if not paper_anchor and not endpoint_anchor:
            reasons.append("target_relevance_not_demonstrated")
        if reasons:
            rejected.append({"edge": edge, "reasons": reasons})
        else:
            accepted.append(edge)
    return accepted, rejected


def build_graph(edges: list[dict]) -> dict:
    """Merge edges into unified graph with provenance."""
    edge_map = defaultdict(lambda: {
        "pmids": [], "years": [], "species": set(),
        "confidences": [], "relations": set(),
        "source_type": "", "target_type": "", "source_refs": [],
                "sessions": set(), "context": {}, "provenance_type": None,
                "provenance_types": set(),
        "claim_ids": [],
    })

    nodes = {}

    for e in edges:
        # Codex extraction may omit optional provenance fields. Preserve the
        # edge with explicit neutral defaults instead of failing the entire
        # run during the deterministic graph stage.
        source = e.get("source")
        target = e.get("target")
        if not source or not target:
            continue
        relation = e.get("relation") or e.get("primary_relation") or "related"
        pmid = e.get("pmid", "")
        pmid_values = e.get("pmids") or ([] if not pmid else [pmid])
        years = e.get("years") or [e.get("year", "")]
        species_values = e.get("species") if isinstance(e.get("species"), list) else [e.get("species", "unknown")]
        confidence = e.get("confidence", 0.5)
        source_type = e.get("source_type", "unknown")
        target_type = e.get("target_type", "unknown")
        context = e.get("context") or {
            "disease": [e["disease"]] if e.get("disease") else [],
            "tissues": e.get("tissues", []),
            "cell_types": e.get("cell_types", []),
            "drugs": e.get("drugs", []),
        }
        provenance_type = e.get("provenance_type") or ("pmid" if pmid else "unknown")
        context_key = json.dumps(context, sort_keys=True, separators=(",", ":"))
        # Relation, polarity, context, and provenance are part of claim identity.
        # Parallel claims are intentional: opposite evidence must not be merged.
        key = (source, target, relation, e.get("polarity"), context_key, provenance_type)
        entry = edge_map[key]
        entry["relations"].add(relation)
        entry["pmids"].extend(pmid_values)
        entry["years"].extend(years)
        entry["species"].update(species_values)
        entry["confidences"].append(confidence)
        entry["source_type"] = source_type
        entry["target_type"] = target_type
        entry["context"] = context
        entry["provenance_type"] = provenance_type
        entry["sessions"].update(e.get("sessions") or ([] if not (e.get("session") or e.get("run_id")) else [e.get("session") or e.get("run_id")]))
        entry["source_refs"].extend(e.get("source_refs") or [])
        if e.get("source_sentence"):
            entry["source_refs"].append({"pmid": pmid, "source_sentence": e["source_sentence"]})
        if e.get("claim_id"):
            entry["claim_ids"].append(e["claim_id"])

        for node, ntype in [(source, source_type), (target, target_type)]:
            if node not in nodes:
                    nodes[node] = {"type": ntype, "pmids": set(), "edge_count": 0, "provenance_types": set()}
            nodes[node]["pmids"].update(pmid_values)
            nodes[node]["edge_count"] += 1
            nodes[node]["provenance_types"].add(provenance_type)

    graph_edges = []
    for (src, tgt, relation, polarity, context_key, provenance_type), data in edge_map.items():
        pmids = sorted({str(pmid) for pmid in data["pmids"] if pmid not in (None, "")})
        avg_conf = sum(data["confidences"]) / len(data["confidences"])
        claim_basis = "|".join([src, tgt, relation, polarity or "", context_key, provenance_type or ""])
        generated_claim_id = "claim_" + hashlib.sha256(claim_basis.encode()).hexdigest()[:16]
        claim_ids = _unique(data["claim_ids"])
        claim_id = claim_ids[0] if len(claim_ids) == 1 else generated_claim_id
        graph_edges.append({
            "claim_id": claim_id,
            "source": src,
            "target": tgt,
            "relations": [relation],
            "primary_relation": relation,
            "polarity": polarity,
            "pmids": pmids,
            "pmid_count": len(pmids),
            "years": sorted(set(data["years"])),
            "species": sorted(data["species"]),
            "confidence": round(avg_conf, 2),
            "evidence_strength": "strong" if len(pmids) >= 3 else ("moderate" if len(pmids) >= 2 else "weak"),
            "source_type": data["source_type"],
            "target_type": data["target_type"],
            "provenance_type": provenance_type,
            "sessions": sorted(data["sessions"]),
            "source_refs": _unique(data["source_refs"]),
            "context": data["context"],
        })

    graph_nodes = []
    for name, data in nodes.items():
        graph_nodes.append({
            "id": name,
            "type": data["type"],
            "pmid_count": len(data["pmids"]),
            "pmids": sorted(pmid for pmid in data["pmids"] if pmid not in (None, "")),
            "edge_count": data["edge_count"],
            "provenance_type": next(iter(data["provenance_types"])) if len(data["provenance_types"]) == 1 else None,
            "provenance_types": sorted(data["provenance_types"]),
        })

    return {"nodes": graph_nodes, "edges": graph_edges}


def merge_graph(existing_graph: dict | None, new_edges: list[dict]) -> dict:
    """Additively merge new evidence into a prior graph.

    Legacy edges are expanded by relation so opposite or previously combined
    relations are not silently collapsed during the migration.
    """
    existing_edges: list[dict] = []
    existing_graph = existing_graph or {}
    for edge in existing_graph.get("edges", []):
        existing_edges.extend(_edge_records(edge))
    merged = build_graph(existing_edges + list(new_edges))
    existing_nodes = {node.get("id"): node for node in existing_graph.get("nodes", []) if node.get("id")}
    current_nodes = {node.get("id") for node in merged["nodes"]}
    for node_id, node in existing_nodes.items():
        if node_id not in current_nodes:
            merged["nodes"].append(node)
    return merged


def validate_graph(graph: dict) -> dict:
    """Agent 6: Detect contradictions, isolated nodes, weak edges."""
    edge_index = defaultdict(list)
    for e in graph["edges"]:
        edge_index[(e["source"], e["target"])].append(e)

    contradictions = []
    suppress_relations = {"suppresses", "inhibits", "reduces"}
    activate_relations = {"activates", "induces", "recruits", "promotes"}

    for e in graph["edges"]:
        rev_key = (e["target"], e["source"])
        for rev in graph["edges"]:
            if rev["source"] == e["target"] and rev["target"] == e["source"]:
                if (e["primary_relation"] in activate_relations and rev["primary_relation"] in suppress_relations) or \
                   (e["primary_relation"] in suppress_relations and rev["primary_relation"] in activate_relations):
                    contradictions.append({
                        "edge_a": f"{e['source']} --{e['primary_relation']}--> {e['target']}",
                        "edge_b": f"{rev['source']} --{rev['primary_relation']}--> {rev['target']}",
                        "pmids_a": e["pmids"],
                        "pmids_b": rev["pmids"],
                    })

    connected = set()
    for e in graph["edges"]:
        connected.add(e["source"])
        connected.add(e["target"])

    isolated = [n for n in graph["nodes"] if n["id"] not in connected or n["edge_count"] == 1]
    weak_edges = [e for e in graph["edges"] if e["evidence_strength"] == "weak"]
    single_paper_edges = [e for e in graph["edges"] if e["pmid_count"] == 1]

    return {
        "contradictions": contradictions,
        "isolated_nodes": [{"id": n["id"], "type": n["type"], "pmid_count": n["pmid_count"]} for n in isolated],
        "weak_edges_count": len(weak_edges),
        "single_paper_edges_count": len(single_paper_edges),
        "weak_edges": weak_edges[:20],
        "single_paper_edges": single_paper_edges[:30],
    }


def discover_architectures(graph: dict) -> list[dict]:
    """Agent 7: Find feedback loops and recurring architectures from topology."""
    adj = defaultdict(list)
    for e in graph["edges"]:
        adj[e["source"]].append((e["target"], e))

    architectures = []

    # Define known architecture signatures
    signatures = [
        {
            "name": "Epithelial alarmin → ILC2 → Type 2 cytokine loop",
            "path": ["Airway epithelium", "IL-33", "ILC2", "IL-5", "Eosinophil"],
            "category": "barrier-immune loop",
        },
        {
            "name": "TSLP-dendritic-Th2 axis",
            "path": ["Airway epithelium", "TSLP", "Dendritic cell", "Th2 cell", "IL-4"],
            "category": "immune education loop",
        },
        {
            "name": "IL-4/IL-13 effector axis",
            "path": ["Th2 cell", "IL-4", "Th2 cell"],
            "category": "positive feedback loop",
        },
        {
            "name": "IL-5 eosinophil amplification",
            "path": ["ILC2", "IL-5", "Eosinophil", "Airway inflammation"],
            "category": "immune amplification loop",
        },
        {
            "name": "Tissue-resident memory chronicity loop",
            "path": ["Batf3", "Dendritic cell", "Tissue-resident memory T cell", "Airway inflammation"],
            "category": "memory loop",
        },
        {
            "name": "Mast cell-IgE effector loop",
            "path": ["Allergen", "IgE", "Mast cell", "Airway inflammation"],
            "category": "effector loop",
        },
        {
            "name": "Bone marrow eosinophilopoiesis axis",
            "path": ["IL-5", "Bone marrow", "Eosinophil"],
            "category": "bone marrow communication",
        },
        {
            "name": "IL-13 remodeling axis",
            "path": ["Th2 cell", "IL-13", "Airway remodeling"],
            "category": "chronic inflammation loop",
        },
        {
            "name": "Biologic intervention (anti-TSLP)",
            "path": ["Tezepelumab", "TSLP", "Type 2 inflammation"],
            "category": "therapeutic interruption",
        },
        {
            "name": "Biologic intervention (anti-IL-4R)",
            "path": ["Dupilumab", "Type 2 inflammation", "Airway inflammation"],
            "category": "therapeutic interruption",
        },
    ]

    node_set = {n["id"] for n in graph["nodes"]}
    edge_set = {(e["source"], e["target"]) for e in graph["edges"]}

    for sig in signatures:
        path = sig["path"]
        nodes_present = [n for n in path if n in node_set]
        edges_present = 0
        supporting_pmids = set()
        total_confidence = 0
        edge_count = 0

        for i in range(len(path) - 1):
            if (path[i], path[i + 1]) in edge_set:
                edges_present += 1
                for e in graph["edges"]:
                    if e["source"] == path[i] and e["target"] == path[i + 1]:
                        supporting_pmids.update(e["pmids"])
                        total_confidence += e["confidence"]
                        edge_count += 1

        completeness = edges_present / (len(path) - 1) if len(path) > 1 else 0
        avg_conf = total_confidence / edge_count if edge_count else 0

        architectures.append({
            "name": sig["name"],
            "category": sig["category"],
            "path": path,
            "nodes_present": len(nodes_present),
            "nodes_total": len(path),
            "edges_present": edges_present,
            "edges_total": len(path) - 1,
            "completeness": round(completeness, 2),
            "supporting_pmids": sorted(supporting_pmids),
            "pmid_count": len(supporting_pmids),
            "avg_confidence": round(avg_conf, 2),
            "rank_score": round(completeness * len(supporting_pmids) * avg_conf, 2),
        })

    architectures.sort(key=lambda x: x["rank_score"], reverse=True)
    return architectures


def identify_gaps(graph: dict, architectures: list[dict]) -> list[dict]:
    """Agent 8: Knowledge gaps for each architecture."""
    edge_set = {(e["source"], e["target"]) for e in graph["edges"]}
    gaps = []

    for arch in architectures:
        path = arch["path"]
        for i in range(len(path) - 1):
            src, tgt = path[i], path[i + 1]
            if (src, tgt) not in edge_set:
                # Check if reverse or indirect exists
                status = "untested"
                if (tgt, src) in edge_set:
                    status = "contradictory"
                elif src in {n["id"] for n in graph["nodes"]} and tgt in {n["id"] for n in graph["nodes"]}:
                    status = "unknown"

                gaps.append({
                    "architecture": arch["name"],
                    "missing_edge": f"{src} → {tgt}",
                    "status": status,
                    "source_in_graph": src in {n["id"] for n in graph["nodes"]},
                    "target_in_graph": tgt in {n["id"] for n in graph["nodes"]},
                })

    single_paper_nodes = [n for n in graph["nodes"] if n["pmid_count"] == 1]
    for n in single_paper_nodes:
        gaps.append({
            "architecture": "global",
            "missing_edge": None,
            "status": "poorly_studied",
            "node": n["id"],
            "pmid": n["pmids"][0] if n["pmids"] else None,
        })

    return gaps


def main():
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_DIR / "mechanisms_extracted.json") as f:
        data = json.load(f)

    graph = build_graph(data["edges"])
    validation = validate_graph(graph)
    architectures = discover_architectures(graph)
    gaps = identify_gaps(graph, architectures)

    output = {
        "metadata": {
            "disease": "Asthma",
            "publication_window": "2021-2026",
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "version": "1.0.0",
        },
        "nodes": graph["nodes"],
        "edges": graph["edges"],
    }

    with open(GRAPH_DIR / "asthma_knowledge_graph.json", "w") as f:
        json.dump(output, f, indent=2)

    with open(GRAPH_DIR / "validation_report.json", "w") as f:
        json.dump(validation, f, indent=2)

    with open(GRAPH_DIR / "architectures.json", "w") as f:
        json.dump(architectures, f, indent=2)

    with open(GRAPH_DIR / "knowledge_gaps.json", "w") as f:
        json.dump(gaps, f, indent=2)

    print(f"Graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    print(f"Contradictions: {len(validation['contradictions'])}")
    print(f"Architectures found: {len(architectures)}")
    print(f"Knowledge gaps: {len(gaps)}")


if __name__ == "__main__":
    main()
