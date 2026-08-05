#!/usr/bin/env python3
"""Export the documented README graph view from one immutable run artifact."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "asthma_20260805T112631Z"
SOURCE = ROOT / "data" / "graphs" / "asthma" / RUN_ID / "knowledge_graph.json"
OUT_DIR = ROOT / "docs" / "assets"
OUT_SVG = OUT_DIR / "asthma-run-20260805T112631Z-pmid-min2.svg"
OUT_META = OUT_DIR / "asthma-run-20260805T112631Z-pmid-min2.metadata.json"

COLORS = {
    "Disease": "#be123c",
    "Gene": "#2563eb",
    "Drug": "#7c3aed",
    "Tissue": "#0891b2",
    "Cell": "#16a34a",
    "Cell_type": "#16a34a",
    "Cytokine": "#e07a3f",
    "Molecule": "#5aa469",
    "Pathway": "#d97706",
    "Clinical_phenotype": "#c23a4b",
}


def main() -> None:
    data = json.loads(SOURCE.read_text())
    source_nodes = {node["id"]: node for node in data["nodes"]}
    source_edges = [edge for edge in data["edges"] if int(edge.get("pmid_count", 0) or 0) >= 2]
    node_ids = {node_id for edge in source_edges for node_id in (edge["source"], edge["target"])}
    graph = nx.MultiDiGraph()
    for node_id in node_ids:
        node = source_nodes[node_id]
        graph.add_node(node_id, **node)
    for edge in source_edges:
        graph.add_edge(edge["source"], edge["target"], **edge)

    pos = nx.spring_layout(graph, seed=42, k=1.25, iterations=250, weight=None)
    fig, ax = plt.subplots(figsize=(15, 9), facecolor="#f7faff")
    ax.set_facecolor("#f7faff")
    node_sizes = [220 + 85 * int(graph.nodes[node].get("pmid_count", 0)) for node in graph.nodes]
    node_colors = [COLORS.get(graph.nodes[node].get("type"), "#94a3b8") for node in graph.nodes]
    edge_widths = [0.8 + 0.45 * int(edge.get("pmid_count", 0)) for _, _, edge in graph.edges(data=True)]
    nx.draw_networkx_edges(
        graph,
        pos,
        ax=ax,
        arrows=True,
        arrowsize=13,
        width=edge_widths,
        edge_color="#718096",
        alpha=0.55,
        connectionstyle="arc3,rad=0.08",
        min_source_margin=8,
        min_target_margin=12,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        ax=ax,
        node_size=node_sizes,
        node_color=node_colors,
        edgecolors="#ffffff",
        linewidths=1.5,
        alpha=0.96,
    )
    labels = {node: node for node in graph.nodes}
    nx.draw_networkx_labels(graph, pos, labels=labels, ax=ax, font_size=7.5, font_weight="bold", font_color="#172033")

    target = data.get("metadata", {}).get("target", {})
    target_text = (
        f"Target dimensions: disease={target.get('disease', 'asthma')} · "
        f"gene={', '.join(target.get('genes', [])) or '—'} · "
        f"drug={', '.join(target.get('drugs', [])) or '—'} · "
        f"tissue={', '.join(target.get('tissues', [])) or '—'} · "
        f"cell type={', '.join(target.get('cell_types', [])) or '—'}"
    )
    ax.set_title("CausalAtlas · Asthma evidence graph", loc="left", fontsize=20, fontweight="bold", color="#172033", pad=18)
    ax.text(0, 1.01, target_text, transform=ax.transAxes, fontsize=9, color="#526174", va="bottom")
    ax.text(
        1,
        1.01,
        f"Run {RUN_ID} · {graph.number_of_nodes()} nodes · {graph.number_of_edges()} edges",
        transform=ax.transAxes,
        fontsize=9,
        color="#526174",
        va="bottom",
        ha="right",
    )
    legend = [
        Line2D([0], [0], marker="o", color="w", label=kind.replace("_", " "), markerfacecolor=color, markersize=9)
        for kind, color in COLORS.items()
        if kind in {graph.nodes[node].get("type") for node in graph.nodes}
    ]
    legend.append(Line2D([0], [0], color="#718096", lw=2, label="edge width = PMID support"))
    ax.legend(handles=legend, loc="lower left", bbox_to_anchor=(0, -0.04), ncol=4, frameon=False, fontsize=8)
    ax.text(
        1,
        -0.045,
        "Filtered view: edge pmid_count ≥ 2; source graph remains unfiltered and auditable.",
        transform=ax.transAxes,
        fontsize=8,
        color="#526174",
        ha="right",
    )
    ax.axis("off")
    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_SVG, format="svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    OUT_META.write_text(
        json.dumps(
            {
                "source": str(SOURCE.relative_to(ROOT)),
                "run_id": RUN_ID,
                "filter": "edge pmid_count >= 2; retain incident nodes",
                "source_node_count": len(data["nodes"]),
                "source_edge_count": len(data["edges"]),
                "exported_node_count": graph.number_of_nodes(),
                "exported_edge_count": graph.number_of_edges(),
                "node_type_colors": COLORS,
            },
            indent=2,
        )
    )
    print(f"Wrote {OUT_SVG} and {OUT_META}")


if __name__ == "__main__":
    main()
