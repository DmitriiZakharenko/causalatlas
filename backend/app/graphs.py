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


def _entity_key(value: object) -> str:
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


def _target_dimensions(metadata: dict) -> dict[str, list[str]]:
    target = metadata.get("target") if isinstance(metadata.get("target"), dict) else {}
    return {
        "Disease": [str(metadata.get("disease"))] if metadata.get("disease") else [],
        "Gene": [str(value) for value in target.get("genes", []) if value],
        "Drug": [str(value) for value in target.get("drugs", []) if value],
        "Tissue": [str(value) for value in target.get("tissues", []) if value],
        "Cell_type": [str(value) for value in target.get("cell_types", []) if value],
    }


def _semantic_type(label: str, base_type: str | None, dimensions: dict[str, list[str]]) -> str | None:
    key = _entity_key(label)
    # Target dimensions are intentionally overlaid on top of extracted
    # biological labels. This identifies the user's requested gene/drug/context
    # without changing the evidence graph or claiming a new biological class.
    compatible_base_types = {
        "Disease": {"Disease", "Clinical_phenotype"},
        "Gene": {"Gene"},
        "Drug": {"Drug", "Molecule"},
        "Tissue": {"Tissue"},
        "Cell_type": {"Cell", "Cell_type"},
    }
    # Do not relabel an evidence node merely because its spelling matches a
    # target alias: IL33 (gene) and IL-33 (cytokine/protein) share a comparison
    # key but are not the same biological role. Canonical source nodes are also
    # kept visibly separate from PMID-derived evidence nodes.
    for entity_type, values in dimensions.items():
        if base_type == "canonical_db":
            continue
        allowed = compatible_base_types.get(entity_type, set())
        if base_type not in allowed:
            continue
        if any(key == _entity_key(value) for value in values):
            return entity_type
    return base_type

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


def _strip_node(node: dict, dimensions: dict[str, list[str]]) -> dict:
    pmids = node.get("pmids") or []
    return {
        "id": node["id"],
        "label": node["id"],
        "type": _semantic_type(node["id"], node.get("type"), dimensions),
        "pmid_count": node.get("pmid_count", len(pmids)),
        "edge_count": node.get("edge_count"),
        "sample_pmids": pmids[:SAMPLE_PMID_LIMIT],
        "provenance_type": node.get("provenance_type"),
        "source": node.get("source"),
        "source_id": node.get("source_id"),
        "is_canonical_source": node.get("is_canonical_source", False),
        "canonical_statement": node.get("canonical_statement", ""),
        "provenance_types": node.get("provenance_types", [node.get("provenance_type")] if node.get("provenance_type") else []),
        "looks_like_noise": _looks_like_extraction_noise(node["id"]),
        "is_input_only": False,
    }


def _input_only_nodes(dimensions: dict[str, list[str]], existing_ids: set[str]) -> list[dict]:
    nodes = []
    for entity_type, values in dimensions.items():
        for value in values:
            node_id = f"__input__{entity_type.casefold()}__{_entity_key(value)}"
            if node_id in existing_ids:
                continue
            nodes.append(
                {
                    "id": node_id,
                    "label": value,
                    "type": entity_type,
                    "pmid_count": 0,
                    "edge_count": 0,
                    "sample_pmids": [],
                    "provenance_type": "input_only",
                    "source": "analysis_target",
                    "source_id": entity_type,
                    "provenance_types": ["input_only"],
                    "looks_like_noise": False,
                    "is_input_only": True,
                }
            )
    return nodes


def _canonical_overlay(
    entries: list[dict],
    existing_nodes: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Build an explicit, non-biological canonical evidence overlay.

    Source hubs make the canonical layer visible without pretending that two
    co-curated biological nodes form a PMID-style causal edge.
    """
    node_ids = {node["id"] for node in existing_nodes}
    overlay_nodes: list[dict] = []
    overlay_edges: list[dict] = []
    for entry in entries:
        entry_id = str(entry.get("entry_id") or entry.get("source_id") or "canonical")
        hub_id = f"__canonical__{entry_id}"
        overlay_nodes.append({
            "id": hub_id,
            "label": f"{entry.get('source', 'canonical')} · {entry_id}",
            "type": "canonical_db",
            "pmid_count": 0,
            "edge_count": len(entry.get("nodes") or []),
            "sample_pmids": [],
            "provenance_type": "canonical_db",
            "source": entry.get("source"),
            "source_id": entry.get("source_id"),
            "provenance_types": ["canonical_db"],
            "looks_like_noise": False,
            "is_input_only": False,
            "is_canonical_source": True,
            "canonical_statement": entry.get("statement", ""),
        })
        for node_id in entry.get("nodes") or []:
            if node_id not in node_ids:
                continue
            overlay_edges.append({
                "id": f"{hub_id}__supports__{node_id}",
                "source": hub_id,
                "target": node_id,
                "relation": "canonical_supports_context",
                "relations": ["canonical_supports_context"],
                "pmid_count": 0,
                "confidence": None,
                "evidence_strength": "canonical",
                "sample_pmids": [],
                "claim_id": f"{hub_id}__supports__{node_id}",
                "provenance_type": "canonical_db",
                "sessions": [],
                "context": {},
                "source_refs": [{
                    "canonical_id": entry_id,
                    "source": entry.get("source"),
                    "source_id": entry.get("source_id"),
                    "statement": entry.get("statement", ""),
                }],
                "contradiction_group": None,
            })
    return overlay_nodes, overlay_edges


def _strip_edge(edge: dict, index: int) -> dict:
    pmids = edge.get("pmids") or []
    return {
        "id": edge.get("claim_id") or f"e{index}__{edge['source']}__{edge['target']}",
        "source": edge["source"],
        "target": edge["target"],
        "relation": edge.get("primary_relation") or edge.get("relation"),
        "relations": edge.get("relations") or ([edge.get("relation")] if edge.get("relation") else []),
        "relation_variants": edge.get("relation_variants") or edge.get("relations") or [],
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
    # The directory is the immutable run identity. Older copied artifacts can
    # contain a stale metadata.run_id from the graph they were based on; never
    # let that value redirect or mislabel a run-scoped graph in the UI.
    if len(parts) == 2:
        source_metadata["run_id"] = parts[1]
        source_metadata["disease_slug"] = disease_slug
    # The UI payload is an explicitly unfiltered view of this source artifact.
    # Keep these labels here as well as in static exports so a filtered client
    # view cannot be mistaken for the persisted graph.
    source_metadata.setdefault("source", str(graph_path))
    source_metadata.setdefault("filter", "unfiltered")
    source_metadata.setdefault("source_node_count", len(raw.get("nodes", [])))
    source_metadata.setdefault("source_edge_count", len(raw.get("edges", [])))
    source_metadata.setdefault("exported_node_count", len(raw.get("nodes", [])))
    source_metadata.setdefault("exported_edge_count", len(raw.get("edges", [])))
    dimensions = _target_dimensions(source_metadata)
    source_metadata["target_dimensions"] = dimensions
    source_nodes = [_strip_node(n, dimensions) for n in raw.get("nodes", [])]
    source_ids = {node["id"] for node in source_nodes}
    input_nodes = _input_only_nodes(dimensions, source_ids)
    canonical_entries = source_metadata.get("canonical_baseline_entries") or []
    if not canonical_entries and source_metadata.get("run_id"):
        session_baseline = REPO_ROOT / "data" / "sessions" / str(source_metadata["run_id"]) / "canonical_baseline.json"
        if session_baseline.exists():
            try:
                baseline = json.loads(session_baseline.read_text())
                canonical_entries = baseline.get("entries") or baseline.get("canonical_entries") or []
            except (OSError, json.JSONDecodeError):
                canonical_entries = []
    canonical_nodes, canonical_edges = _canonical_overlay(canonical_entries, source_nodes)
    source_metadata["exported_node_count"] = len(source_nodes) + len(input_nodes) + len(canonical_nodes)
    # The response contains explicit input-only target nodes in addition to
    # evidence nodes. Keep source_node_count above as the persisted-graph
    # count, while node_count describes what the user actually sees.
    source_metadata["node_count"] = len(source_nodes) + len(input_nodes) + len(canonical_nodes)
    source_metadata["edge_count"] = len(raw.get("edges", [])) + len(canonical_edges)
    source_metadata["canonical_overlay_node_count"] = len(canonical_nodes)
    source_metadata["canonical_overlay_edge_count"] = len(canonical_edges)
    return {
        "metadata": source_metadata,
        "elements": {
            "nodes": source_nodes + input_nodes + canonical_nodes,
            "edges": [_strip_edge(e, i) for i, e in enumerate(raw.get("edges", []))] + canonical_edges,
        },
    }
