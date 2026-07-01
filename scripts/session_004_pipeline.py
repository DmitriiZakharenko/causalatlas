#!/usr/bin/env python3
"""
Session 004 — Graph hardening (no hypothesis generation).
Agent 4 full-corpus extraction, Agent 8 full contradiction scan, noise audit, architecture re-verify, full viz.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from extract_mechanisms import extract_from_abstract, classify_node, NODE_ALIASES  # noqa: E402

DATA = ROOT / "data"
GRAPH = ROOT / "graph"
VIZ = GRAPH / "visualizations"
REPORTS = ROOT / "reports"

ACTIVATE = {"activates", "induces", "recruits", "promotes", "maintains", "differentiates_into"}
SUPPRESS = {"suppresses", "inhibits", "blocks", "reduces"}

ARCHITECTURES = [
    ("Epithelial alarmin → ILC2 → Type 2 cytokine loop", ["Airway epithelium", "IL-33", "ILC2", "IL-5", "Eosinophil"]),
    ("Mast cell-IgE effector loop", ["Allergen", "IgE", "Mast cell", "Airway inflammation"]),
    ("IL-5 eosinophil amplification", ["ILC2", "IL-5", "Eosinophil", "Airway inflammation"]),
    ("IL-4/IL-13 Th2 positive feedback", ["Th2 cell", "IL-4", "Th2 cell"]),
    ("IL-13 remodeling axis", ["Th2 cell", "IL-13", "Airway remodeling"]),
    ("Bone marrow eosinophilopoiesis axis", ["IL-5", "Bone marrow", "Eosinophil"]),
    ("TSLP-dendritic-Th2 axis", ["Airway epithelium", "TSLP", "Dendritic cell", "Th2 cell", "IL-4"]),
    ("Tissue-resident memory chronicity loop", ["Batf3", "Dendritic cell", "Tissue-resident memory T cell", "Airway inflammation"]),
    ("Biologic anti-TSLP", ["Tezepelumab", "TSLP", "Type 2 inflammation"]),
    ("Biologic anti-IL-4R", ["Dupilumab", "Type 2 inflammation", "Airway inflammation"]),
]

CANONICAL_NODES = {
    "IL-4", "IL-5", "IL-13", "IL-33", "IL-25", "TSLP", "IL-12", "ILC2", "ILC3", "Th2 cell", "Th17 cell",
    "Eosinophil", "Neutrophil", "Mast cell", "Basophil", "Dendritic cell", "cDC1", "Goblet cell",
    "Fibroblast", "Tissue-resident memory T cell", "Innate immune cell", "Airway epithelium",
    "Intestinal epithelium", "Lung", "Airway", "Bone marrow", "IgE", "GATA3", "STAT6", "Batf3", "ST2",
    "IL-4R", "IL-5R", "IL-13R", "Allergen", "House dust mite", "Type 2 inflammation",
    "Airway inflammation", "Airway hyperresponsiveness", "Airway remodeling", "Mucus hypersecretion",
    "Dupilumab", "Mepolizumab", "Benralizumab", "Tezepelumab", "Omalizumab", "Trained immunity",
    "Airway smooth muscle", "NOD2", "TNF", "IL-23", "IL-22", "Epithelial barrier", "Intestinal inflammation",
}
CANONICAL_NODES.update(NODE_ALIASES.values())

ARTIFACT_RE = [
    re.compile(r"^(They|We|This|These|While|However|Mainly|Only|Our|Such|Experimental|Sustained|Type-2|Type 2)\b", re.I),
    re.compile(r"transcription factor|transcriptional program|encoding gene|chemokine receptor-encoding", re.I),
    re.compile(r"^(A|An|The)\s+[A-Z]", re.I),
    re.compile(r"inflammation and tissue damage|strongly reduced|have strongly", re.I),
    re.compile(r"^type-?\s*2\s+(cytokines|inflammation is|endotype)", re.I),
    re.compile(r"^(mscs|mice|patients|results|conclusion|background|methods)\b", re.I),
]


def is_artifact_node(node_id: str) -> tuple[bool, str]:
    if node_id in CANONICAL_NODES:
        return False, ""
    if node_id in {"And", "Or", "The", "In", "To", "Of", "For", "With", "By"}:
        return True, "stopword_node"
    low = node_id.lower().strip()
    if low in {a.lower() for a in NODE_ALIASES}:
        return False, ""
    # short valid tokens
    if re.match(r"^IL-?\d+[a-z]?$", node_id, re.I):
        return False, ""
    if len(node_id.split()) > 6:
        return True, "too_many_words"
    for pat in ARTIFACT_RE:
        if pat.search(node_id):
            return True, f"pattern:{pat.pattern[:40]}"
    # Title-case sentence fragment heuristic
    words = node_id.split()
    if len(words) >= 3 and words[0][0].isupper() and not any(
        w.lower() in {"il", "cd", "th", "tslp", "ige", "hdm", "trm", "ilc", "dc", "ahr"} for w in words
    ):
        if not re.search(r"\b(cell|cells|cytokine|receptor|antibody|mab|epithelium|inflammation|asthma|marrow|allergen)\b", low):
            return True, "sentence_fragment"
    return False, ""


def extract_all_edges(papers: list[dict]) -> tuple[list[dict], dict]:
    all_edges = []
    papers_with_edges = 0
    log = []
    for p in papers:
        conf = p.get("quality", {}).get("confidence_score", 0.5)
        edges = extract_from_abstract(p.get("abstract", ""), p["pmid"], p.get("year", ""), p.get("species", "unknown"), conf)
        if edges:
            papers_with_edges += 1
            for e in edges:
                e["evidence_sentence"] = e.get("evidence_sentence", "")
            all_edges.extend(edges)
            log.append({"pmid": p["pmid"], "count": len(edges)})
    stats = {
        "total_papers": len(papers),
        "papers_with_edges": papers_with_edges,
        "total_raw_edges": len(all_edges),
    }
    return all_edges, stats


def build_edge_map(edges: list[dict]) -> dict:
    edge_map = {}
    for e in edges:
        key = (e["source"], e["target"], e["relation"])
        if key not in edge_map:
            edge_map[key] = {
                "source": e["source"], "target": e["target"],
                "primary_relation": e["relation"], "relations": [e["relation"]],
                "pmids": [], "evidence_sentences": {}, "years": [], "species": set(),
                "confidences": [], "source_type": e["source_type"], "target_type": e["target_type"],
            }
        entry = edge_map[key]
        if e["pmid"] not in entry["pmids"]:
            entry["pmids"].append(e["pmid"])
        entry["evidence_sentences"][e["pmid"]] = e.get("evidence_sentence", "")
        entry["years"].append(e.get("year", ""))
        entry["species"].add(e.get("species", "unknown"))
        entry["confidences"].append(e.get("confidence", 0.5))
    return edge_map


def merge_edge_maps(existing_edges: list[dict], new_edge_map: dict) -> dict:
    """Non-destructive: union PMIDs from existing graph into rebuilt map."""
    merged = dict(new_edge_map)
    for e in existing_edges:
        rel = e.get("primary_relation", (e.get("relations") or ["induces"])[0])
        key = (e["source"], e["target"], rel)
        if key not in merged:
            merged[key] = {
                "source": e["source"], "target": e["target"],
                "primary_relation": rel, "relations": e.get("relations", [rel]),
                "pmids": list(e.get("pmids", [])),
                "evidence_sentences": dict(e.get("evidence_sentences", {})),
                "years": e.get("years", []), "species": set(e.get("species", [])),
                "confidences": [e.get("confidence", 0.5)],
                "source_type": e.get("source_type", ""), "target_type": e.get("target_type", ""),
            }
        else:
            for pmid in e.get("pmids", []):
                if pmid not in merged[key]["pmids"]:
                    merged[key]["pmids"].append(pmid)
                if pmid in e.get("evidence_sentences", {}):
                    merged[key]["evidence_sentences"][pmid] = e["evidence_sentences"][pmid]
    return merged


def edge_map_to_graph(edge_map: dict, metadata: dict) -> dict:
    edges = []
    nodes = defaultdict(lambda: {"type": "", "pmids": set(), "edge_count": 0})
    for entry in edge_map.values():
        n = len(entry["pmids"])
        conf = sum(entry["confidences"]) / max(len(entry["confidences"]), 1)
        edges.append({
            "source": entry["source"], "target": entry["target"],
            "primary_relation": entry["primary_relation"],
            "relations": sorted(set(entry["relations"])),
            "pmids": sorted(entry["pmids"], key=lambda x: int(x) if str(x).isdigit() else 0),
            "pmid_count": n,
            "evidence_sentences": entry["evidence_sentences"],
            "years": sorted(set(x for x in entry["years"] if x)),
            "species": sorted(entry["species"]) if isinstance(entry["species"], set) else entry["species"],
            "confidence": round(conf, 2),
            "evidence_strength": "strong" if n >= 3 else ("moderate" if n >= 2 else "weak"),
            "source_type": entry["source_type"], "target_type": entry["target_type"],
        })
        for node, nt in [(entry["source"], entry["source_type"]), (entry["target"], entry["target_type"])]:
            nodes[node]["type"] = nt
            nodes[node]["pmids"].update(entry["pmids"])
            nodes[node]["edge_count"] += 1
    graph_nodes = [
        {"id": k, "type": v["type"], "pmid_count": len(v["pmids"]),
         "pmids": sorted(v["pmids"], key=lambda x: int(x) if str(x).isdigit() else 0),
         "edge_count": v["edge_count"]}
        for k, v in nodes.items()
    ]
    meta = dict(metadata)
    meta["node_count"] = len(graph_nodes)
    meta["edge_count"] = len(edges)
    return {
        "metadata": meta,
        "nodes": graph_nodes,
        "edges": edges,
    }


def noise_audit_and_clean(graph: dict) -> tuple[dict, dict]:
    removed_nodes = []
    for n in graph["nodes"]:
        bad, reason = is_artifact_node(n["id"])
        if bad:
            removed_nodes.append({"id": n["id"], "reason": reason, "pmid_count": n.get("pmid_count", 0)})
    remove_set = {r["id"] for r in removed_nodes}
    clean_edges = [e for e in graph["edges"] if e["source"] not in remove_set and e["target"] not in remove_set]
    # rebuild nodes from clean edges
    nodes = defaultdict(lambda: {"type": "", "pmids": set(), "edge_count": 0})
    for e in clean_edges:
        for node, nt in [(e["source"], e["source_type"]), (e["target"], e["target_type"])]:
            nodes[node]["type"] = nt
            nodes[node]["pmids"].update(e["pmids"])
            nodes[node]["edge_count"] += 1
    clean_nodes = [
        {"id": k, "type": v["type"], "pmid_count": len(v["pmids"]),
         "pmids": sorted(v["pmids"], key=lambda x: int(x) if str(x).isdigit() else 0),
         "edge_count": v["edge_count"]}
        for k, v in nodes.items()
    ]
    meta = dict(graph["metadata"])
    meta["node_count"] = len(clean_nodes)
    meta["edge_count"] = len(clean_edges)
    meta["noise_cleaned"] = True
    audit = {
        "nodes_before": len(graph["nodes"]),
        "nodes_after": len(clean_nodes),
        "nodes_removed": len(removed_nodes),
        "edges_before": len(graph["edges"]),
        "edges_after": len(clean_edges),
        "edges_removed": len(graph["edges"]) - len(clean_edges),
        "removed_nodes": removed_nodes,
    }
    return {"metadata": meta, "nodes": clean_nodes, "edges": clean_edges}, audit


def full_contradiction_scan(graph: dict) -> dict:
    """Agent 8: all directed pairs with ≥2 edge records or conflicting relations."""
    pair_edges = defaultdict(list)
    for e in graph["edges"]:
        pair_edges[(e["source"], e["target"])].append(e)

    contradictions = []
    seen = set()

    for (src, tgt), edges in pair_edges.items():
        if len(edges) < 2:
            # single edge with multiple relations?
            if len(edges) == 1:
                rels = set(edges[0].get("relations", [edges[0]["primary_relation"]]))
                if rels & ACTIVATE and rels & SUPPRESS:
                    cid = f"{src}->{tgt}:multi_rel"
                    contradictions.append({
                        "id": cid,
                        "node_pair": [src, tgt],
                        "type": "multi_relation_single_edge",
                        "relations": sorted(rels),
                        "pmids": edges[0]["pmids"],
                    })
            continue

        # multiple edge records same direction
        all_rels = set()
        for e in edges:
            all_rels.add(e["primary_relation"])
            all_rels.update(e.get("relations", []))
        if all_rels & ACTIVATE and all_rels & SUPPRESS:
            cid = f"{src}->{tgt}:conflict"
            if cid not in seen:
                seen.add(cid)
                contradictions.append({
                    "id": cid,
                    "node_pair": [src, tgt],
                    "type": "opposing_relations_same_direction",
                    "edges": [
                        {"relation": e["primary_relation"], "pmids": e["pmids"], "pmid_count": e["pmid_count"]}
                        for e in edges
                    ],
                    "resolution": "UNRESOLVED",
                })

    # reverse-direction conflicts
    edge_index = {(e["source"], e["target"]): e for e in graph["edges"]}
    checked = set()
    for (src, tgt), e_fwd in edge_index.items():
        key = tuple(sorted([src, tgt]))
        if key in checked:
            continue
        checked.add(key)
        e_rev = edge_index.get((tgt, src))
        if not e_rev:
            continue
        fwd_act = e_fwd["primary_relation"] in ACTIVATE
        fwd_sup = e_fwd["primary_relation"] in SUPPRESS
        rev_act = e_rev["primary_relation"] in ACTIVATE
        rev_sup = e_rev["primary_relation"] in SUPPRESS
        if (fwd_act and rev_sup) or (fwd_sup and rev_act):
            contradictions.append({
                "id": f"{src}<->{tgt}:reverse",
                "node_pair": [src, tgt],
                "type": "opposing_directions",
                "edge_a": {"source": src, "target": tgt, "relation": e_fwd["primary_relation"], "pmids": e_fwd["pmids"]},
                "edge_b": {"source": tgt, "target": src, "relation": e_rev["primary_relation"], "pmids": e_rev["pmids"]},
                "resolution": "UNRESOLVED",
            })

    # preserve Batf3 manual contradiction if present
    batf3 = [c for c in contradictions if "Batf3" in str(c)]
    return {
        "session": "004",
        "scan_type": "full_graph_all_pairs",
        "pairs_with_multiple_edges": sum(1 for v in pair_edges.values() if len(v) >= 2),
        "contradiction_count": len(contradictions),
        "contradictions": sorted(contradictions, key=lambda x: x["id"]),
        "batf3_contradictions_found": len(batf3),
    }


def verify_architectures(graph: dict) -> list[dict]:
    edge_set = {(e["source"], e["target"]) for e in graph["edges"]}
    results = []
    for name, path in ARCHITECTURES:
        present_edges = 0
        missing = []
        pmids = set()
        for i in range(len(path) - 1):
            s, t = path[i], path[i + 1]
            if (s, t) in edge_set:
                present_edges += 1
                for e in graph["edges"]:
                    if e["source"] == s and e["target"] == t:
                        pmids.update(e["pmids"])
            else:
                missing.append(f"{s} → {t}")
        comp = present_edges / max(len(path) - 1, 1)
        results.append({
            "name": name,
            "path": path,
            "edges_present": present_edges,
            "edges_total": len(path) - 1,
            "completeness": round(comp, 2),
            "completeness_session001_claim": comp == 1.0,
            "missing_edges": missing,
            "pmid_count": len(pmids),
            "under_extracted_risk": comp < 1.0 and any("→" in m for m in missing),
        })
    return results


def compute_loops_and_metrics(graph: dict) -> tuple[dict, dict]:
    """Agent 6/7 baseline: architecture loops + centrality on core nodes."""
    CORE = CANONICAL_NODES
    signatures = [
        ("Epithelial-ILC2-T2", ["Airway epithelium", "IL-33", "ILC2", "IL-5", "Eosinophil"]),
        ("TSLP-Type2", ["Airway epithelium", "TSLP", "Type 2 inflammation"]),
        ("Th2-feedback", ["Th2 cell", "IL-4", "Th2 cell"]),
        ("IL5-marrow", ["IL-5", "Bone marrow", "Eosinophil"]),
        ("Mast-IgE", ["Allergen", "IgE", "Mast cell", "Airway inflammation"]),
        ("Batf3-TRM", ["Batf3", "Dendritic cell", "Tissue-resident memory T cell", "Airway inflammation"]),
    ]
    # aggregate all edges per directed pair (multiple relations may exist)
    pair_edges = defaultdict(list)
    for e in graph["edges"]:
        pair_edges[(e["source"], e["target"])].append(e)

    loops = []
    for name, path in signatures:
        pmids = set()
        strengths = []
        present = 0
        for i in range(len(path) - 1):
            edges = pair_edges.get((path[i], path[i + 1]), [])
            if edges:
                present += 1
                for e in edges:
                    pmids.update(e["pmids"])
                    strengths.append(e["pmid_count"])
        loops.append({
            "name": name, "path": path,
            "edges_present": present, "edges_total": len(path) - 1,
            "completeness": round(present / max(len(path) - 1, 1), 2),
            "pmid_count": len(pmids),
            "min_edge_pmid_count": min(strengths) if strengths else 0,
            "max_edge_pmid_count": max(strengths) if strengths else 0,
            "avg_edge_pmid_count": round(sum(strengths) / len(strengths), 1) if strengths else 0,
            "supporting_pmids": sorted(pmids, key=lambda x: int(x) if str(x).isdigit() else 0)[:50],
        })

    G = nx.DiGraph()
    for e in graph["edges"]:
        if e["source"] in CORE or e["target"] in CORE:
            G.add_edge(e["source"], e["target"], weight=e["pmid_count"])
    degree = dict(G.degree())
    try:
        betweenness = nx.betweenness_centrality(G) if len(G) < 500 else {}
        pagerank = nx.pagerank(G) if len(G) < 500 else {}
    except Exception:
        betweenness, pagerank = {}, {}
    top_degree = sorted(degree.items(), key=lambda x: -x[1])[:25]
    metrics = {
        "session": "004",
        "baseline_for_future_sessions": True,
        "total_nodes": graph["metadata"]["node_count"],
        "total_edges": graph["metadata"]["edge_count"],
        "core_subgraph_nodes": len(G),
        "core_subgraph_edges": G.number_of_edges(),
        "degree_centrality_top25": dict(top_degree),
        "betweenness_top15": dict(sorted(betweenness.items(), key=lambda x: -x[1])[:15]),
        "pagerank_top15": dict(sorted(pagerank.items(), key=lambda x: -x[1])[:15]),
        "cycle_count_architecture_loops_complete": sum(1 for l in loops if l["completeness"] == 1.0),
        "cycle_count_architecture_loops_total": len(loops),
    }
    return {"loops": loops, "cycle_count": len(loops)}, metrics


def export_graph_viz(graph: dict, out_dir: Path, name: str, label: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / name
    G = nx.DiGraph()
    for n in graph["nodes"]:
        G.add_node(n["id"], node_type=n.get("type", ""))
    for e in graph["edges"]:
        G.add_edge(e["source"], e["target"], relation=e.get("primary_relation", ""))
    nx.write_graphml(G, str(base.with_suffix(".graphml")))
    nx.write_gexf(G, str(base.with_suffix(".gexf")))
    n = len(G)
    k = 2.0 / math.sqrt(max(n, 1))
    pos = nx.spring_layout(G, seed=42, k=k) if n <= 200 else nx.spring_layout(G, seed=42, k=0.15)
    figsize = (max(12, min(36, n * 0.08)), max(10, min(28, n * 0.06)))
    fig, ax = plt.subplots(figsize=figsize)
    if n <= 300:
        nx.draw_networkx_nodes(G, pos, node_size=max(80, 800 - n * 2), node_color="#4C78A8", alpha=0.75, ax=ax)
        nx.draw_networkx_labels(G, pos, font_size=max(4, 8 - n // 80), ax=ax)
        nx.draw_networkx_edges(G, pos, edge_color="#666", arrows=True, arrowsize=8, width=0.5, ax=ax, alpha=0.5)
    else:
        nx.draw_networkx_nodes(G, pos, node_size=15, node_color="#4C78A8", alpha=0.5, ax=ax)
        nx.draw_networkx_edges(G, pos, edge_color="#999", arrows=False, width=0.2, ax=ax, alpha=0.25)
    ax.set_title(label, fontsize=12)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(base.with_suffix(".png"), dpi=150 if n < 200 else 100, bbox_inches="tight")
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    return {"view": name, "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
            "graphml": str(base.with_suffix(".graphml")), "gexf": str(base.with_suffix(".gexf")),
            "png": str(base.with_suffix(".png")), "svg": str(base.with_suffix(".svg"))}


def main():
    ts = datetime.now(timezone.utc).isoformat()
    with open(DATA / "publications_merged_s002.json") as f:
        corpus = json.load(f)
    with open(DATA / "publications_verified.json") as f:
        s001 = json.load(f)
    with open(GRAPH / "knowledge_graph.json") as f:
        graph_before = json.load(f)

    s001_pmids = {p["pmid"] for p in s001}
    new_papers = [p for p in corpus if p["pmid"] not in s001_pmids]

    pre_nodes = graph_before["metadata"]["node_count"]
    pre_edges = graph_before["metadata"]["edge_count"]

    # Agent 4 — full corpus extraction
    print("Agent 4: extracting from full corpus...")
    raw_edges, extract_stats = extract_all_edges(corpus)
    new_raw = [e for e in raw_edges if e["pmid"] not in s001_pmids]
    new_pmids_with_edges = len({e["pmid"] for e in new_raw})
    s001_reextract = [e for e in raw_edges if e["pmid"] in s001_pmids]
    s001_pmids_with_edges = len({e["pmid"] for e in s001_reextract})

    new_edge_map = build_edge_map(raw_edges)
    merged_map = merge_edge_maps(graph_before["edges"], new_edge_map)
    graph_merged = edge_map_to_graph(merged_map, {
        **graph_before["metadata"],
        "version": "3.0.0",
        "session": "004",
        "updated": ts,
        "extraction": "full_corpus_rerun",
    })

    # Noise audit
    print("Noise audit...")
    graph_clean, noise_audit = noise_audit_and_clean(graph_merged)
    graph_clean["metadata"]["version"] = "3.0.0"
    graph_clean["metadata"]["session"] = "004"
    graph_clean["metadata"]["updated"] = ts

    # Agent 8
    print("Agent 8: contradiction scan...")
    contradictions = full_contradiction_scan(graph_clean)
    # append curated Batf3 if not auto-detected
    if not any("Batf3" in c.get("id", "") for c in contradictions["contradictions"]):
        old = json.load(open(GRAPH / "contradictions.json")) if (GRAPH / "contradictions.json").exists() else {}
        for c in old.get("contradictions", []):
            if c.get("id", "").startswith("BATF3"):
                contradictions["contradictions"].insert(0, c)
                contradictions["contradiction_count"] += 1

    # Architecture re-verify
    print("Architecture re-verify...")
    arch_results = verify_architectures(graph_clean)

    # Loops + metrics baseline
    loops_data, metrics = compute_loops_and_metrics(graph_clean)

    # Save graph
    for path in [GRAPH / "knowledge_graph.json", GRAPH / "asthma_knowledge_graph.json"]:
        with open(path, "w") as f:
            json.dump(graph_clean, f, indent=2)

    with open(GRAPH / "contradictions.json", "w") as f:
        json.dump(contradictions, f, indent=2)
    with open(GRAPH / "noise_audit.json", "w") as f:
        json.dump(noise_audit, f, indent=2)
    with open(GRAPH / "loops.json", "w") as f:
        json.dump(loops_data["loops"], f, indent=2)
    with open(GRAPH / "network_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    with open(GRAPH / "architectures.json", "w") as f:
        json.dump(arch_results, f, indent=2)

    # Visualizations
    print("Exporting true full graph...")
    true_full = export_graph_viz(
        graph_clean, VIZ / "true_full_graph", "true_full_graph",
        f"Asthma KG — TRUE FULL GRAPH ({graph_clean['metadata']['node_count']} nodes, {graph_clean['metadata']['edge_count']} edges)",
    )
    # rename semantics: evidence-filtered view
    filtered = export_graph_viz(
        {"metadata": graph_clean["metadata"],
         "nodes": [n for n in graph_clean["nodes"] if n["pmid_count"] >= 2],
         "edges": [e for e in graph_clean["edges"] if e["pmid_count"] >= 2]},
        VIZ / "evidence_filtered_graph", "evidence_filtered_graph",
        f"Asthma KG — evidence-filtered (pmid_count≥2): {len([n for n in graph_clean['nodes'] if n['pmid_count']>=2])} nodes",
    )

    quality = {
        "session": "004",
        "updated": ts,
        "agent4_extraction": {
            "full_corpus_papers": len(corpus),
            "papers_with_edges_full_corpus": extract_stats["papers_with_edges"],
            "papers_with_edges_rate": f"{extract_stats['papers_with_edges']}/{len(corpus)}",
            "session001_baseline": "337/448",
            "session002_new_papers_in_merged": len(new_papers),
            "session002_new_papers_with_edges": new_pmids_with_edges,
            "session002_new_papers_with_edges_rate": f"{new_pmids_with_edges}/{len(new_papers)}",
            "session002_new_pmids_retrieved_original": 1576,
            "session001_reextract_with_edges": s001_pmids_with_edges,
            "total_raw_edges_extracted": extract_stats["total_raw_edges"],
        },
        "graph_counts": {
            "pre_session004_nodes": pre_nodes,
            "pre_session004_edges": pre_edges,
            "post_extraction_pre_noise_nodes": len(graph_merged["nodes"]),
            "post_extraction_pre_noise_edges": len(graph_merged["edges"]),
            "post_noise_nodes": graph_clean["metadata"]["node_count"],
            "post_noise_edges": graph_clean["metadata"]["edge_count"],
            "delta_edges_vs_session002_graph": graph_clean["metadata"]["edge_count"] - pre_edges,
            "delta_nodes_vs_session002_graph": graph_clean["metadata"]["node_count"] - pre_nodes,
        },
        "noise_audit_summary": {
            "nodes_removed": noise_audit["nodes_removed"],
            "edges_removed": noise_audit["edges_removed"],
        },
        "agent8_contradictions": contradictions["contradiction_count"],
        "architecture_reverification": arch_results,
        "loops_baseline": {"cycle_count": loops_data["cycle_count"], "complete_loops": metrics["cycle_count_architecture_loops_complete"]},
        "visualizations": {"true_full_graph": true_full, "evidence_filtered_graph": filtered},
        "note": "Session 004 graph hardening only — no hypothesis generation.",
    }
    with open(GRAPH / "graph_quality_report.json", "w") as f:
        json.dump(quality, f, indent=2)

    with open(DATA / "mechanisms_extracted_s004.json", "w") as f:
        json.dump({"edges": raw_edges, "stats": extract_stats}, f)

    manifest_path = VIZ / "visualization_manifest.json"
    manifest = json.load(open(manifest_path)) if manifest_path.exists() else {"views": []}
    manifest["session_004"] = {
        "true_full_graph": true_full,
        "evidence_filtered_graph": filtered,
        "note": "Prior 'full_graph' (63 nodes) was mislabeled evidence-filtered subset; use true_full_graph for complete export.",
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    (REPORTS / "session_004_diff.md").write_text(
        f"# Session 004 — Graph Hardening\n\n"
        f"- Extraction: {extract_stats['papers_with_edges']}/{len(corpus)} papers with edges\n"
        f"- New papers (S002): {new_pmids_with_edges}/{len(new_papers)} with edges\n"
        f"- Graph: {pre_nodes}/{pre_edges} → {graph_clean['metadata']['node_count']}/{graph_clean['metadata']['edge_count']}\n"
        f"- Noise removed: {noise_audit['nodes_removed']} nodes, {noise_audit['edges_removed']} edges\n"
        f"- Contradictions: {contradictions['contradiction_count']}\n"
        f"- True full graph: {true_full['nodes']} nodes exported\n"
    )

    print(json.dumps(quality["graph_counts"], indent=2))
    print(f"Extraction: {extract_stats['papers_with_edges']}/{len(corpus)}")
    print(f"New papers: {new_pmids_with_edges}/{len(new_papers)}")
    print(f"Noise removed: {noise_audit['nodes_removed']} nodes")
    print(f"Contradictions: {contradictions['contradiction_count']}")


if __name__ == "__main__":
    main()
