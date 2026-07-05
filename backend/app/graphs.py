"""
Phase 5: serves `data/graphs/<disease>/knowledge_graph.json` to the frontend
in a small, cytoscape.js-ready shape.

The on-disk files store the FULL PMID list per node/edge (this is what makes
`data/graphs/asthma/knowledge_graph.json` ~1.1MB for 838 nodes / 1143 edges)
-- that provenance detail matters for the pipeline and for a human auditing a
specific edge, but a graph-rendering client only needs a `pmid_count` (for
visual weight) plus a small citable sample, not the full list every time.
This module is the one place that does that stripping, so the frontend never
has to parse megabytes of PMIDs just to draw a node.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRAPHS_DIR = REPO_ROOT / "data" / "graphs"

SAMPLE_PMID_LIMIT = 5


class GraphNotFoundError(LookupError):
    pass


def list_available_graphs() -> list[dict]:
    """One entry per `data/graphs/<disease>/knowledge_graph.json` found on
    disk -- metadata only, no nodes/edges (cheap enough to call on every
    page load of a disease picker)."""
    graphs = []
    if not GRAPHS_DIR.exists():
        return graphs
    for disease_dir in sorted(GRAPHS_DIR.iterdir()):
        graph_path = disease_dir / "knowledge_graph.json"
        if not graph_path.exists():
            continue
        raw = json.loads(graph_path.read_text())
        metadata = raw.get("metadata", {})
        graphs.append(
            {
                "disease_slug": disease_dir.name,
                "disease": metadata.get("disease", disease_dir.name),
                "node_count": metadata.get("node_count", len(raw.get("nodes", []))),
                "edge_count": metadata.get("edge_count", len(raw.get("edges", []))),
                "version": metadata.get("version"),
                "updated": metadata.get("updated"),
            }
        )
    return graphs


def _strip_node(node: dict) -> dict:
    pmids = node.get("pmids") or []
    return {
        "id": node["id"],
        "label": node["id"],
        "type": node.get("type"),
        "pmid_count": node.get("pmid_count", len(pmids)),
        "edge_count": node.get("edge_count"),
        "sample_pmids": pmids[:SAMPLE_PMID_LIMIT],
    }


def _strip_edge(edge: dict, index: int) -> dict:
    pmids = edge.get("pmids") or []
    return {
        "id": f"e{index}__{edge['source']}__{edge['target']}",
        "source": edge["source"],
        "target": edge["target"],
        "relation": edge.get("primary_relation"),
        "relations": edge.get("relations"),
        "pmid_count": edge.get("pmid_count", len(pmids)),
        "confidence": edge.get("confidence"),
        "evidence_strength": edge.get("evidence_strength"),
        "sample_pmids": pmids[:SAMPLE_PMID_LIMIT],
    }


def load_graph_for_ui(disease_slug: str) -> dict:
    """Returns `{"metadata": {...}, "elements": {"nodes": [...], "edges": [...]}}`
    -- the `elements` shape matches what `react-cytoscapejs` expects almost
    verbatim (it wraps each in `{"data": ...}` on the frontend side, kept
    there rather than here so this stays plain, easily-tested JSON).
    """
    graph_path = GRAPHS_DIR / disease_slug / "knowledge_graph.json"
    if not graph_path.exists():
        raise GraphNotFoundError(f"no graph found for disease slug {disease_slug!r}")
    raw = json.loads(graph_path.read_text())
    return {
        "metadata": raw.get("metadata", {}),
        "elements": {
            "nodes": [_strip_node(n) for n in raw.get("nodes", [])],
            "edges": [_strip_edge(e, i) for i, e in enumerate(raw.get("edges", []))],
        },
    }
