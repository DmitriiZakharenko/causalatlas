#!/usr/bin/env python3
"""
Agents 5-8: Knowledge graph builder, validator, architecture discovery, gap analysis.
"""
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GRAPH_DIR = Path(__file__).resolve().parent.parent / "graph"


def build_graph(edges: list[dict]) -> dict:
    """Merge edges into unified graph with provenance."""
    edge_map = defaultdict(lambda: {
        "pmids": [], "years": [], "species": set(),
        "confidences": [], "relations": set(),
        "source_type": "", "target_type": "",
    })

    nodes = {}

    for e in edges:
        key = (e["source"], e["target"])
        entry = edge_map[key]
        entry["relations"].add(e["relation"])
        entry["pmids"].append(e["pmid"])
        entry["years"].append(e["year"])
        entry["species"].add(e["species"])
        entry["confidences"].append(e["confidence"])
        entry["source_type"] = e["source_type"]
        entry["target_type"] = e["target_type"]

        for node, ntype in [(e["source"], e["source_type"]), (e["target"], e["target_type"])]:
            if node not in nodes:
                nodes[node] = {"type": ntype, "pmids": set(), "edge_count": 0}
            nodes[node]["pmids"].add(e["pmid"])
            nodes[node]["edge_count"] += 1

    graph_edges = []
    for (src, tgt), data in edge_map.items():
        pmids = list(set(data["pmids"]))
        avg_conf = sum(data["confidences"]) / len(data["confidences"])
        graph_edges.append({
            "source": src,
            "target": tgt,
            "relations": sorted(data["relations"]),
            "primary_relation": max(data["relations"], key=lambda r: list(data["relations"]).count(r)) if len(data["relations"]) == 1 else sorted(data["relations"])[0],
            "pmids": pmids,
            "pmid_count": len(pmids),
            "years": sorted(set(data["years"])),
            "species": sorted(data["species"]),
            "confidence": round(avg_conf, 2),
            "evidence_strength": "strong" if len(pmids) >= 3 else ("moderate" if len(pmids) >= 2 else "weak"),
            "source_type": data["source_type"],
            "target_type": data["target_type"],
        })

    graph_nodes = []
    for name, data in nodes.items():
        graph_nodes.append({
            "id": name,
            "type": data["type"],
            "pmid_count": len(data["pmids"]),
            "pmids": sorted(data["pmids"]),
            "edge_count": data["edge_count"],
        })

    return {"nodes": graph_nodes, "edges": graph_edges}


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
