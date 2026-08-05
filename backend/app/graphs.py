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

# Some on-disk graphs (e.g. asthma Session 004) already went through the
# source pipeline's own noise-cleaning passes (see graph_quality_report.json's
# "pattern_artifact_heuristics" + "stopword_node_cleanup") and still ended up
# with ~40% of nodes being leftover sentence-fragment extraction artifacts
# ("Suggesting", "And Effectively", "Number Of Total Asthma Exacerbations")
# rather than real biological entities. This is a best-effort *display*
# heuristic on top of that -- it never edits the underlying file, it just
# flags nodes so the UI can offer a declutter toggle. Not a ground-truth
# classifier: expect both false positives and false negatives.
_NOISE_WORDS = {
    "and", "or", "but", "by", "of", "in", "on", "at", "to", "is", "was", "were",
    "are", "be", "been", "the", "a", "an", "then", "also", "through", "thereby",
    "therefore", "thus", "hence", "which", "that", "this", "these", "those",
    "can", "could", "may", "might", "will", "would", "it", "its", "their",
    "they", "suggesting", "showing", "revealing", "indicating", "demonstrating",
    "indicates", "shows", "reveals", "suggests", "significantly", "markedly",
    "ultimately", "primarily", "whereas", "while", "after", "before", "both",
    "from", "with", "as", "not", "no", "so", "such", "than", "completely",
    "demonstrated", "revealed", "showed", "expressed", "induced", "reduced",
    "increased", "decreased", "enhanced", "promoted", "inhibited", "activated",
    "downregulated", "upregulated", "regulates", "mediates", "triggers",
    "causes", "leads", "results", "led", "result",
}


def _looks_like_extraction_noise(label: str) -> bool:
    words = label.split()
    if not words:
        return True
    lowered = [w.strip(".,;:").lower() for w in words]
    if len(words) >= 5:
        return True
    if lowered[0] in _NOISE_WORDS or lowered[-1] in _NOISE_WORDS:
        return True
    if len(words) >= 3 and any(w in _NOISE_WORDS for w in lowered):
        return True
    if words[0].isdigit():
        return True
    if len(words) >= 2 and all(w in _NOISE_WORDS for w in lowered):
        return True
    return False


class GraphNotFoundError(LookupError):
    pass


def list_available_graphs() -> list[dict]:
    """One entry per `data/graphs/<disease>/knowledge_graph.json` found on
    disk -- metadata only, no nodes/edges (cheap enough to call on every
    page load of a disease picker)."""
    graphs = []
    if not GRAPHS_DIR.exists():
        return graphs
    graph_paths = sorted(GRAPHS_DIR.glob("*/knowledge_graph.json"))
    graph_paths += sorted(GRAPHS_DIR.glob("*/*/knowledge_graph.json"))
    for graph_path in graph_paths:
        disease_dir = graph_path.parent.parent if graph_path.parent.parent != GRAPHS_DIR else graph_path.parent
        raw = json.loads(graph_path.read_text())
        metadata = raw.get("metadata", {})
        graph_key = "__".join(graph_path.relative_to(GRAPHS_DIR).parent.parts)
        graphs.append(
            {
                "disease_slug": graph_key,
                "disease": metadata.get("disease", disease_dir.name),
                "node_count": metadata.get("node_count", len(raw.get("nodes", []))),
                "edge_count": metadata.get("edge_count", len(raw.get("edges", []))),
                "version": metadata.get("version"),
                "updated": metadata.get("updated"),
                "run_id": graph_path.parent.name if graph_path.parent.parent != GRAPHS_DIR else None,
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
        "provenance_type": node.get("provenance_type"),
        "source": node.get("source"),
        "source_id": node.get("source_id"),
        "provenance_types": node.get("provenance_types", [node.get("provenance_type")] if node.get("provenance_type") else []),
        "looks_like_noise": _looks_like_extraction_noise(node["id"]),
    }


def _strip_edge(edge: dict, index: int) -> dict:
    pmids = edge.get("pmids") or []
    return {
        "id": edge.get("claim_id") or f"e{index}__{edge['source']}__{edge['target']}",
        "source": edge["source"],
        "target": edge["target"],
        "relation": edge.get("primary_relation") or edge.get("relation"),
        "relations": edge.get("relations") or ([edge.get("relation")] if edge.get("relation") else []),
        "pmid_count": edge.get("pmid_count", len(pmids)),
        "confidence": edge.get("confidence"),
        "evidence_strength": edge.get("evidence_strength"),
        "sample_pmids": pmids[:SAMPLE_PMID_LIMIT],
        "claim_id": edge.get("claim_id"),
        "provenance_type": edge.get("provenance_type"),
        "sessions": edge.get("sessions", []),
        "context": edge.get("context", {}),
        "source_refs": edge.get("source_refs", []),
        "contradiction_group": edge.get("contradiction_group"),
    }


def load_graph_for_ui(disease_slug: str) -> dict:
    """Returns `{"metadata": {...}, "elements": {"nodes": [...], "edges": [...]}}`
    -- the `elements` shape matches what `react-cytoscapejs` expects almost
    verbatim (it wraps each in `{"data": ...}` on the frontend side, kept
    there rather than here so this stays plain, easily-tested JSON).
    """
    parts = disease_slug.split("__", 1)
    graph_path = (GRAPHS_DIR / parts[0] / parts[1] / "knowledge_graph.json") if len(parts) == 2 else (GRAPHS_DIR / disease_slug / "knowledge_graph.json")
    if not graph_path.exists():
        raise GraphNotFoundError(f"no graph found for disease slug {disease_slug!r}")
    raw = json.loads(graph_path.read_text())
    source_metadata = dict(raw.get("metadata", {}))
    # The UI payload is an explicitly unfiltered view of this source artifact.
    # Keep these labels here as well as in static exports so a filtered client
    # view cannot be mistaken for the persisted graph.
    source_metadata.setdefault("source", str(graph_path))
    source_metadata.setdefault("filter", "unfiltered")
    source_metadata.setdefault("source_node_count", len(raw.get("nodes", [])))
    source_metadata.setdefault("source_edge_count", len(raw.get("edges", [])))
    source_metadata.setdefault("exported_node_count", len(raw.get("nodes", [])))
    source_metadata.setdefault("exported_edge_count", len(raw.get("edges", [])))
    return {
        "metadata": source_metadata,
        "elements": {
            "nodes": [_strip_node(n) for n in raw.get("nodes", [])],
            "edges": [_strip_edge(e, i) for i, e in enumerate(raw.get("edges", []))],
        },
    }
