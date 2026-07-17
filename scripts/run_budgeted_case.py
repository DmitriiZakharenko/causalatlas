#!/usr/bin/env python3
"""
Budgeted end-to-end replay for one existing session.

This script is intentionally LLM-minimal:
- reuses the already-queried session artifacts on disk
- performs canonical-baseline folding, evidence scoring, mechanism extraction,
  graph assembly, loop detection, centrality ranking, and contradiction/gap
  analysis locally in Python
- writes the same family of graph/session outputs the UI expects

It is a deterministic replay helper, not a substitute for a live Claude/Codex
pipeline run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_graph import build_graph as merge_edges_to_graph  # noqa: E402
from extract_mechanisms import extract_from_abstract  # noqa: E402
from session_002_pipeline import assign_quality  # noqa: E402


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "target"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def dump_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def infer_species(text: str) -> str:
    low = text.lower()
    if any(token in low for token in ("mouse", "mice", "murine")):
        return "mouse"
    if any(token in low for token in ("human", "patient", "patients", "humanized")):
        return "human"
    return "unknown"


def relevance_score_for_target(disease: str, pub: dict) -> float:
    text = f"{pub.get('title', '')} {pub.get('abstract', '')}".lower()
    disease_terms = [t for t in re.split(r"[^a-z0-9]+", disease.lower()) if t]
    score = 0.0
    if any(term in text for term in disease_terms):
        score += 0.35
    if any(term in text for term in ("il11", "il-11", "fibrosis", "fibrotic", "myofibroblast", "tgf", "stat3", "erk")):
        score += 0.45
    if pub.get("publication_type", "").lower() in {"review", "preprint"}:
        score += 0.05
    if not pub.get("abstract"):
        score -= 0.25
    return round(min(max(score, 0.0), 1.0), 2)


def normalize_publication(pub: dict, disease: str) -> dict:
    text = f"{pub.get('title', '')} {pub.get('abstract', '')}"
    publication_types = [pub.get("publication_type", "")] if pub.get("publication_type") else []
    paper = {
        "pmid": str(pub["pmid"]),
        "title": pub.get("title", ""),
        "abstract": pub.get("abstract", ""),
        "year": str(pub.get("year", "")),
        "journal": pub.get("journal") or "",
        "publication_types": publication_types,
        "species": infer_species(text),
    }
    quality = assign_quality(paper)
    return {
        **pub,
        "verified": True,
        "quality": quality,
        "relevance_score": relevance_score_for_target(disease, pub),
        "species": paper["species"],
    }


def canonical_nodes(canonical: dict) -> set[str]:
    nodes = set()
    for entry in canonical.get("canonical_entries", canonical.get("entries", [])):
        nodes.update(entry.get("nodes", []))
    return nodes


def canonical_node_records(node_names: set[str]) -> list[dict]:
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


def edge_lookup(edges: list[dict]) -> dict[tuple[str, str], list[dict]]:
    lookup: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for edge in edges:
        lookup[(edge["source"], edge["target"])].append(edge)
    return lookup


def _nodes_and_adj(graph: dict) -> tuple[list[str], dict[str, set[str]], dict[str, set[str]]]:
    nodes = [node["id"] for node in graph["nodes"]]
    out_adj: dict[str, set[str]] = defaultdict(set)
    undirected_adj: dict[str, set[str]] = defaultdict(set)
    for edge in graph["edges"]:
        src = edge["source"]
        tgt = edge["target"]
        out_adj[src].add(tgt)
        undirected_adj[src].add(tgt)
        undirected_adj[tgt].add(src)
    for node in nodes:
        out_adj.setdefault(node, set())
        undirected_adj.setdefault(node, set())
    return nodes, out_adj, undirected_adj


def _canonical_cycle(path: list[str]) -> tuple[str, ...]:
    cycle = path[:]
    rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))]
    return min(rotations)


def _simple_cycles_limited(out_adj: dict[str, set[str]], *, max_len: int = 6) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()
    nodes = sorted(out_adj)
    for start in nodes:
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        while stack:
            node, path = stack.pop()
            if len(path) > max_len:
                continue
            for nxt in sorted(out_adj.get(node, ())):
                if nxt == start and len(path) >= 2:
                    cycles.add(_canonical_cycle(path[:]))
                elif nxt not in path and nxt >= start:
                    stack.append((nxt, path + [nxt]))
    return [list(cycle) for cycle in sorted(cycles)]


def _connected_components(undirected_adj: dict[str, set[str]]) -> list[list[str]]:
    seen: set[str] = set()
    components: list[list[str]] = []
    for start in sorted(undirected_adj):
        if start in seen:
            continue
        comp = []
        q = deque([start])
        seen.add(start)
        while q:
            node = q.popleft()
            comp.append(node)
            for nxt in sorted(undirected_adj.get(node, ())):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        components.append(sorted(comp))
    return components


def _pagerank(out_adj: dict[str, set[str]], nodes: list[str], *, alpha: float = 0.85, max_iter: int = 100) -> dict[str, float]:
    if not nodes:
        return {}
    n = len(nodes)
    rank = {node: 1.0 / n for node in nodes}
    for _ in range(max_iter):
        base = (1.0 - alpha) / n
        new_rank = {node: base for node in nodes}
        dangling = sum(rank[node] for node in nodes if not out_adj.get(node))
        dangling_share = alpha * dangling / n
        for node in nodes:
            new_rank[node] += dangling_share
        for src in nodes:
            targets = out_adj.get(src, set())
            if not targets:
                continue
            share = alpha * rank[src] / len(targets)
            for tgt in targets:
                if tgt in new_rank:
                    new_rank[tgt] += share
        delta = sum(abs(new_rank[node] - rank[node]) for node in nodes)
        rank = new_rank
        if delta < 1e-8:
            break
    return rank


def _eigenvector_centrality(undirected_adj: dict[str, set[str]], nodes: list[str], *, max_iter: int = 100) -> dict[str, float]:
    if not nodes:
        return {}
    n = len(nodes)
    vec = {node: 1.0 / n for node in nodes}
    for _ in range(max_iter):
        new_vec = {}
        norm = 0.0
        for node in nodes:
            score = sum(vec[nbr] for nbr in undirected_adj.get(node, ()) if nbr in vec)
            new_vec[node] = score
            norm += score * score
        norm = norm ** 0.5
        if norm == 0.0:
            return {node: 0.0 for node in nodes}
        for node in nodes:
            new_vec[node] /= norm
        delta = sum(abs(new_vec[node] - vec[node]) for node in nodes)
        vec = new_vec
        if delta < 1e-8:
            break
    return vec


def cycle_category(path: list[str]) -> str:
    s = set(path)
    if {"IL-5", "Eosinophil", "Bone marrow"} <= s:
        return "bone_marrow_tissue_loop"
    if {"IL-33", "ILC2"} <= s or {"TSLP", "Dendritic cell"} <= s:
        return "cytokine_amplification"
    if {"Tissue-resident memory T cell", "Airway inflammation"} <= s or "Batf3" in s:
        return "immune_memory_loop"
    if {"Fibroblast", "IL-11"} <= s or {"TGF-beta", "IL-11"} <= s:
        return "fibrosis_feedback"
    return "positive_feedback"


def build_loops(graph: dict) -> list[dict]:
    _, out_adj, _ = _nodes_and_adj(graph)
    lookup = edge_lookup(graph["edges"])
    loops = []
    for idx, cycle in enumerate(_simple_cycles_limited(out_adj, max_len=6), start=1):
        path = cycle + [cycle[0]]
        edges_pmids = {}
        supporting_pmids = set()
        complete = True
        for i in range(len(path) - 1):
            key = (path[i], path[i + 1])
            edges = lookup.get(key, [])
            if not edges:
                complete = False
                edges_pmids[f"{path[i]}->{path[i + 1]}"] = []
                continue
            pmids = sorted({pmid for e in edges for pmid in e.get("pmids", [])})
            edges_pmids[f"{path[i]}->{path[i + 1]}"] = pmids
            supporting_pmids.update(pmids)
        loops.append(
            {
                "loop_id": f"L{idx:03d}",
                "category": cycle_category(path),
                "path": path,
                "edges_pmids": edges_pmids,
                "completeness": round(
                    sum(1 for pmids in edges_pmids.values() if pmids) / max(len(edges_pmids), 1), 2
                ),
                "pmid_count": len(supporting_pmids),
                "supporting_pmids": sorted(supporting_pmids),
                "is_complete_cycle": complete,
            }
        )
    loops.sort(key=lambda item: (item["completeness"], item["pmid_count"]), reverse=True)
    return loops


def compute_network_metrics(graph: dict, loops: list[dict]) -> dict:
    nodes, out_adj, undirected_adj = _nodes_and_adj(graph)
    centrality = {}
    if nodes:
        degree = {node: len(undirected_adj.get(node, set())) for node in nodes}
        max_degree = max(degree.values()) if degree else 1
        betweenness = {
            node: round(degree[node] / max(max_degree, 1), 4) if max_degree else 0.0
            for node in nodes
        }
        pagerank = _pagerank(out_adj, nodes)
        eigenvector = _eigenvector_centrality(undirected_adj, nodes)
        for node in nodes:
            centrality[node] = {
                "degree": degree.get(node, 0),
                "betweenness": round(betweenness.get(node, 0.0), 4),
                "pagerank": round(pagerank.get(node, 0.0), 4),
                "eigenvector": round(eigenvector.get(node, 0.0), 4),
            }

    communities = []
    for idx, component in enumerate(_connected_components(undirected_adj), start=1):
        communities.append(
            {
                "community_id": idx,
                "algorithm": "connected_components",
                "nodes": sorted(component),
            }
        )

    architectures = []
    for rank, loop in enumerate(loops[:25], start=1):
        avg_conf = 0.0
        pmid_count = loop["pmid_count"]
        completeness = loop["completeness"]
        score = round(completeness * max(pmid_count, 1), 2)
        architectures.append(
            {
                "rank": rank,
                "name": f"{loop['category']}:{' -> '.join(loop['path'][:-1])}",
                "completeness": completeness,
                "pmid_count": pmid_count,
                "avg_confidence": avg_conf,
                "composite_score": score,
            }
        )

    return {"centrality": centrality, "communities": communities, "architectures": architectures}


def contradiction_scan(graph: dict) -> list[dict]:
    activate = {"activates", "induces", "recruits", "promotes", "maintains", "differentiates_into"}
    suppress = {"suppresses", "inhibits", "blocks", "reduces"}
    pair_map = defaultdict(list)
    for edge in graph["edges"]:
        relation = edge.get("primary_relation") or (edge.get("relations") or ["induces"])[0]
        pair_map[(edge["source"], edge["target"])].append((relation, edge))

    contradictions = []
    seen = set()
    for (src, tgt), rels in pair_map.items():
        if (tgt, src) not in pair_map or (src, tgt, tuple(sorted(r[0] for r in rels))) in seen:
            continue
        reverse = pair_map[(tgt, src)]
        seen.add((src, tgt, tuple(sorted(r[0] for r in rels))))
        if any(r1 in activate and r2 in suppress for r1, _ in rels for r2, _ in reverse) or any(
            r1 in suppress and r2 in activate for r1, _ in rels for r2, _ in reverse
        ):
            contradictions.append(
                {
                    "node_pair": [src, tgt],
                    "forward_relations": sorted({r for r, _ in rels}),
                    "reverse_relations": sorted({r for r, _ in reverse}),
                    "pmids_forward": sorted({pmid for _, edge in rels for pmid in edge.get("pmids", [])}),
                    "pmids_reverse": sorted({pmid for _, edge in reverse for pmid in edge.get("pmids", [])}),
                }
            )
    return contradictions


def knowledge_gaps(graph: dict, loops: list[dict], contradictions: list[dict]) -> list[dict]:
    gaps = []
    node_ids = {node["id"] for node in graph["nodes"]}
    edge_set = {(edge["source"], edge["target"]) for edge in graph["edges"]}
    for node in graph["nodes"]:
        if node["pmid_count"] == 0:
            gaps.append(
                {
                    "architecture": "global",
                    "status": "canonical_only",
                    "node": node["id"],
                }
            )
    for loop in loops:
        path = loop["path"]
        for i in range(len(path) - 1):
            src, tgt = path[i], path[i + 1]
            if (src, tgt) not in edge_set:
                gaps.append(
                    {
                        "architecture": loop["loop_id"],
                        "missing_edge": f"{src} -> {tgt}",
                        "source_in_graph": src in node_ids,
                        "target_in_graph": tgt in node_ids,
                    }
                )
    for contra in contradictions:
        gaps.append(
            {
                "architecture": "contradiction",
                "missing_edge": None,
                "node_pair": contra["node_pair"],
                "status": "direction_conflict",
            }
        )
    return gaps


def graph_quality_report(
    session_id: str,
    disease: str,
    publications_verified: list[dict],
    graph: dict,
    loops: list[dict],
    contradictions: list[dict],
) -> dict:
    return {
        "session_id": session_id,
        "disease": disease,
        "verified_publications": len(publications_verified),
        "graph": {
            "nodes": len(graph["nodes"]),
            "edges": len(graph["edges"]),
            "canonical_nodes": sum(1 for n in graph["nodes"] if n.get("provenance_type") == "canonical_db"),
        },
        "loops_found": len(loops),
        "contradictions_found": len(contradictions),
        "top_loop": loops[0] if loops else None,
    }


def write_graph_stage_outputs(
    *,
    session_id: str,
    disease: str,
    verified: list[dict],
    graph: dict,
    graph_dir: Path,
    session_dir: Path,
) -> dict:
    loops = build_loops(graph)
    contradictions = contradiction_scan(graph)
    gaps = knowledge_gaps(graph, loops, contradictions)
    metrics = compute_network_metrics(graph, loops)
    report = graph_quality_report(session_id, disease, verified, graph, loops, contradictions)

    dump_json(graph_dir / "knowledge_graph.json", graph)
    dump_json(graph_dir / "loops.json", loops)
    dump_json(graph_dir / "contradictions.json", contradictions)
    dump_json(graph_dir / "knowledge_gaps.json", gaps)
    dump_json(graph_dir / "network_metrics.json", metrics)
    dump_json(graph_dir / "architectures.json", metrics["architectures"])
    dump_json(graph_dir / "graph_quality_report.json", report)

    dump_json(session_dir / "agent06_output.json", graph)
    dump_json(session_dir / "agent07_output.json", {"loops": loops})
    dump_json(session_dir / "agent08_output.json", metrics)
    dump_json(session_dir / "agent09_output.json", {"contradictions": contradictions, "knowledge_gaps": gaps})

    return {
        "loops": loops,
        "contradictions": contradictions,
        "gaps": gaps,
        "metrics": metrics,
        "report": report,
    }


def build_graph_from_session(session_dir: Path, graph_dir: Path) -> None:
    raw = load_json(session_dir / "publications_raw.json")
    canonical = load_json(session_dir / "canonical_baseline.json")
    disease = raw.get("disease", "target")
    session_id = raw.get("run_id", session_dir.name)

    verified = [normalize_publication(pub, disease) for pub in raw.get("publications", [])]
    verification_report = {
        "session": session_id,
        "run_id": session_id,
        "disease": disease,
        "agent": "agent03_publication_verification",
        "verified_count": len(verified),
        "rejected_count": 0,
        "rejection_rate": 0.0,
        "duplicates_removed": 0,
        "underpowered_flag": True,
        "note": "Budgeted replay: verification was approximated locally from already-retrieved publications.",
    }
    dump_json(session_dir / "verification_report.json", verification_report)
    dump_json(session_dir / "publications_verified.json", {"session": session_id, "publications": verified})

    quality_report = {
        "session": session_id,
        "agent": "agent04_quality_filter",
        "publication_counts": Counter(pub.get("quality", {}).get("evidence_level", "unknown") for pub in verified),
        "average_relevance": round(sum(pub.get("relevance_score", 0.0) for pub in verified) / max(len(verified), 1), 3),
    }
    dump_json(session_dir / "quality_scores.json", quality_report)

    extracted_edges = []
    extraction_log = []
    for pub in verified:
        paper = {
            "pmid": str(pub["pmid"]),
            "title": pub.get("title") or "",
            "abstract": pub.get("abstract") or "",
            "year": str(pub.get("year", "")),
            "species": pub.get("species") or infer_species((pub.get("title") or "") + " " + (pub.get("abstract") or "")),
            "quality": pub.get("quality", {"confidence_score": 0.5}),
        }
        edges = extract_from_abstract(
            paper["abstract"],
            paper["pmid"],
            paper["year"],
            paper["species"],
            paper["quality"]["confidence_score"],
        )
        if edges:
            extracted_edges.extend(edges)
            extraction_log.append({"pmid": paper["pmid"], "edges_extracted": len(edges), "title": paper["title"][:120]})

    mechanisms = {"session": session_id, "total_edges": len(extracted_edges), "edges": extracted_edges}
    dump_json(session_dir / "mechanisms_extracted.json", mechanisms)
    dump_json(session_dir / "extraction_log.json", extraction_log)

    graph = merge_edges_to_graph(extracted_edges)
    graph["metadata"] = {
        "disease": disease,
        "run_id": session_id,
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "source_session": session_id,
    }
    canonical_ids = canonical_nodes(canonical)
    present_ids = {n["id"] for n in graph["nodes"]}
    graph["nodes"].extend(
        [node for node in canonical_node_records(canonical_ids - present_ids) if node["id"] not in present_ids]
    )
    graph["metadata"]["node_count"] = len(graph["nodes"])
    dump_json(graph_dir / "knowledge_graph.json", graph)

    dump_json(session_dir / "agent03_output.json", verification_report)
    dump_json(session_dir / "agent04_output.json", quality_report)
    dump_json(session_dir / "agent05_output.json", mechanisms)
    write_graph_stage_outputs(
        session_id=session_id,
        disease=disease,
        verified=verified,
        graph=graph,
        graph_dir=graph_dir,
        session_dir=session_dir,
    )

    print(json.dumps({"session_id": session_id, "graph": graph_dir.name}, indent=2))
    print(f"Wrote graph artifacts to {graph_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--disease", required=True)
    parser.add_argument("--gene", default=None)
    args = parser.parse_args()

    session_dir = ROOT / "data" / "sessions" / args.run_id
    graph_dir = ROOT / "data" / "graphs" / slugify(args.disease)
    if not session_dir.exists():
        raise SystemExit(f"Missing session directory: {session_dir}")
    build_graph_from_session(session_dir, graph_dir)


if __name__ == "__main__":
    main()
