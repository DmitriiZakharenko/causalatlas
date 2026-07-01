#!/usr/bin/env python3
"""
Visualization pipeline for asthma knowledge graph (Session 002 completion).
Exports 7 views × 4 formats without modifying the graph.
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = ROOT / "graph" / "knowledge_graph.json"
OUT = ROOT / "graph" / "visualizations"
LOOPS_PATH = ROOT / "graph" / "loops.json"
MODULES_PATH = ROOT / "graph" / "modules.json"

CORE_NODES = {
    "IL-4", "IL-5", "IL-13", "IL-33", "IL-25", "TSLP", "ILC2", "Th2 cell", "Eosinophil",
    "Neutrophil", "Mast cell", "Dendritic cell", "cDC1", "Airway epithelium", "IgE",
    "GATA3", "Batf3", "Tissue-resident memory T cell", "Type 2 inflammation",
    "Airway inflammation", "Airway hyperresponsiveness", "Airway remodeling",
    "Bone marrow", "Dupilumab", "Mepolizumab", "Benralizumab", "Tezepelumab",
    "Omalizumab", "Allergen", "House dust mite", "Mucus hypersecretion", "IL-12", "ST2",
}

BONE_MARROW_NODES = {
    "IL-5", "Bone marrow", "Eosinophil", "Eosinophilopoiesis", "Type 2 inflammation",
    "ILC2", "Th2 cell", "Mepolizumab", "Benralizumab",
}

EPITHELIAL_NODES = {
    "Airway epithelium", "TSLP", "IL-33", "IL-25", "ILC2", "Dendritic cell", "Th2 cell",
    "Type 2 inflammation", "Goblet cell", "House dust mite", "Allergen", "ST2",
}

CYTOKINE_NODES = {
    "IL-4", "IL-5", "IL-13", "IL-33", "IL-25", "TSLP", "IL-12",
}

THERAPEUTIC_NODES = {
    "Dupilumab", "Mepolizumab", "Benralizumab", "Tezepelumab", "Omalizumab",
    "TSLP", "IL-4", "IL-5", "IL-13", "IgE", "Eosinophil", "Type 2 inflammation",
    "Airway inflammation",
}

TYPE_COLORS = {
    "Cell": "#4C78A8",
    "Cytokine": "#F58518",
    "Molecule": "#54A24B",
    "Tissue": "#B279A2",
    "Clinical_phenotype": "#E45756",
    "Pathway": "#72B7B2",
    "default": "#9D9D9D",
}


def load_graph_data() -> tuple[dict, list, list]:
    with open(GRAPH_PATH) as f:
        data = json.load(f)
    return data, data["nodes"], data["edges"]


def build_nx_graph(
    nodes: list[dict],
    edges: list[dict],
    node_filter: set[str] | None = None,
    include_neighbors: bool = False,
) -> nx.DiGraph:
    G = nx.DiGraph()
    node_map = {n["id"]: n for n in nodes}

    if node_filter:
        selected = set(node_filter) & set(node_map)
        if include_neighbors:
            for e in edges:
                if e["source"] in node_filter or e["target"] in node_filter:
                    selected.add(e["source"])
                    selected.add(e["target"])
        nodes_to_add = [node_map[n] for n in selected if n in node_map]
    else:
        # Master: core nodes + their interconnecting edges only (readable layout)
        selected = set(CORE_NODES) & set(node_map)
        for e in edges:
            if e["source"] in selected and e["target"] in selected:
                pass
            elif e["source"] in CORE_NODES or e["target"] in CORE_NODES:
                selected.add(e["source"])
                selected.add(e["target"])
        nodes_to_add = [node_map[n] for n in selected if n in node_map]

    for n in nodes_to_add:
        G.add_node(n["id"], node_type=n.get("type", "default"), pmid_count=n.get("pmid_count", 0))

    for e in edges:
        if e["source"] in G and e["target"] in G:
            rel = e.get("primary_relation", (e.get("relations") or ["induces"])[0])
            G.add_edge(
                e["source"],
                e["target"],
                relation=rel,
                pmid_count=e.get("pmid_count", len(e.get("pmids", []))),
                pmids=",".join(e.get("pmids", [])[:5]),
            )
    return G


def build_loop_graph(nodes: list, edges: list, loops: list) -> nx.DiGraph:
    loop_nodes: set[str] = set()
    for lp in loops:
        loop_nodes.update(lp["path"])
    return build_nx_graph(nodes, edges, loop_nodes, include_neighbors=False)


def build_community_graph(nodes: list, edges: list, modules: dict) -> nx.DiGraph:
    G = nx.DiGraph()
    node_map = {n["id"]: n for n in nodes}
    module_of = {}
    for mod, members in modules.items():
        for m in members:
            module_of[m] = mod
    for mod, members in modules.items():
        for m in members:
            if m in node_map:
                G.add_node(m, node_type=node_map[m].get("type", "default"), module=mod)
    for e in edges:
        if e["source"] in G and e["target"] in G:
            rel = e.get("primary_relation", (e.get("relations") or ["induces"])[0])
            G.add_edge(e["source"], e["target"], relation=rel)
    return G


def export_graphml_gexf(G: nx.DiGraph, base_path: Path) -> None:
    nx.write_graphml(G, str(base_path.with_suffix(".graphml")))
    nx.write_gexf(G, str(base_path.with_suffix(".gexf")))


def layout_graph(G: nx.DiGraph) -> dict:
    if len(G) == 0:
        return {}
    if len(G) <= 25:
        return nx.spring_layout(G, seed=42, k=1.8)
    return nx.spring_layout(G, seed=42, k=1.2 / math.sqrt(len(G)))


def draw_graph(G: nx.DiGraph, title: str, base_path: Path, highlight: set[str] | None = None) -> None:
    if len(G) == 0:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No nodes in view", ha="center", va="center")
        ax.set_title(title)
        fig.savefig(base_path.with_suffix(".png"), dpi=150, bbox_inches="tight")
        fig.savefig(base_path.with_suffix(".svg"), bbox_inches="tight")
        plt.close(fig)
        return

    pos = layout_graph(G)
    fig_w = max(10, min(24, len(G) * 0.35))
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * 0.75))

    node_colors = []
    for n in G.nodes():
        if highlight and n in highlight:
            node_colors.append("#FF2D00")
        else:
            ntype = G.nodes[n].get("node_type", "default")
            node_colors.append(TYPE_COLORS.get(ntype, TYPE_COLORS["default"]))

    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=900, alpha=0.92, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=7, font_weight="bold", ax=ax)
    nx.draw_networkx_edges(
        G, pos, edge_color="#666666", arrows=True, arrowsize=12,
        connectionstyle="arc3,rad=0.1", width=1.2, ax=ax,
    )

    edge_labels = {(u, v): d.get("relation", "")[:10] for u, v, d in G.edges(data=True)}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=5, ax=ax)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(base_path.with_suffix(".png"), dpi=150, bbox_inches="tight")
    fig.savefig(base_path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def export_view(name: str, G: nx.DiGraph, title: str, highlight: set[str] | None = None) -> dict:
    view_dir = OUT / name
    view_dir.mkdir(parents=True, exist_ok=True)
    base = view_dir / name
    export_graphml_gexf(G, base)
    draw_graph(G, title, base, highlight=highlight)
    return {
        "view": name,
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "graphml": str(base.with_suffix(".graphml")),
        "gexf": str(base.with_suffix(".gexf")),
        "png": str(base.with_suffix(".png")),
        "svg": str(base.with_suffix(".svg")),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data, nodes, edges = load_graph_data()
    with open(LOOPS_PATH) as f:
        loops = json.load(f)
    with open(MODULES_PATH) as f:
        modules = json.load(f)

    manifest = []

    # 1. Master graph (core-focused readable subgraph)
    G_master = build_nx_graph(nodes, edges, CORE_NODES, include_neighbors=True)
    manifest.append(export_view("master_graph", G_master, "Asthma Knowledge Graph — Master (Core Subgraph)"))

    # 2. Loop graph
    G_loops = build_loop_graph(nodes, edges, loops)
    manifest.append(export_view("loop_graph", G_loops, "Asthma Knowledge Graph — Feedback Loops"))

    # 3. Community graph (modules.json)
    G_comm = build_community_graph(nodes, edges, modules)
    manifest.append(export_view("community_graph", G_comm, "Asthma Knowledge Graph — Community Modules"))

    # 4. Bone marrow axis
    G_bm = build_nx_graph(nodes, edges, BONE_MARROW_NODES, include_neighbors=True)
    manifest.append(export_view("bone_marrow_axis_graph", G_bm, "Asthma Knowledge Graph — Bone Marrow Axis"))

    # 5. Epithelial interactions
    G_epi = build_nx_graph(nodes, edges, EPITHELIAL_NODES, include_neighbors=True)
    manifest.append(export_view("epithelial_interaction_graph", G_epi, "Asthma Knowledge Graph — Epithelial Interactions"))

    # 6. Cytokine network
    G_cyt = build_nx_graph(nodes, edges, CYTOKINE_NODES, include_neighbors=True)
    manifest.append(export_view("cytokine_network", G_cyt, "Asthma Knowledge Graph — Cytokine Network"))

    # 7. Therapeutic target overlay
    G_ther = build_nx_graph(nodes, edges, THERAPEUTIC_NODES, include_neighbors=True)
    manifest.append(export_view(
        "therapeutic_target_overlay",
        G_ther,
        "Asthma Knowledge Graph — Therapeutic Target Overlay",
        highlight={"Dupilumab", "Mepolizumab", "Benralizumab", "Tezepelumab", "Omalizumab"},
    ))

    manifest_path = OUT / "visualization_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({"source": str(GRAPH_PATH), "views": manifest}, f, indent=2)

    print(json.dumps(manifest, indent=2))
    print(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    main()
