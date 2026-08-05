import json
import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import visualize_graph


def test_export_graph_uses_multidigraph_and_claim_keys(tmp_path):
    nodes = [{"id": "A", "type": "Cell"}, {"id": "B", "type": "Cytokine"}]
    edges = [
        {"source": "A", "target": "B", "claim_id": "claim_1", "primary_relation": "activates", "pmids": ["1"]},
        {"source": "A", "target": "B", "claim_id": "claim_2", "primary_relation": "inhibits", "pmids": ["2", "3"]},
    ]
    graph = visualize_graph.build_nx_graph(nodes, edges, {"A", "B"})
    assert isinstance(graph, nx.MultiDiGraph)
    assert graph.number_of_edges() == 2
    # The key is the stable claim ID, so parallel evidence is addressable.
    assert {key for _, _, key in graph.edges(keys=True)} == {"claim_1", "claim_2"}

    base = tmp_path / "graph_pmid_min2"
    visualize_graph.export_graphml_gexf(graph, base, {
        "source": "knowledge_graph.json", "filter": "pmid_count >= 2",
        "source_node_count": 2, "source_edge_count": 2,
    })
    loaded = nx.read_graphml(base.with_suffix(".graphml"))
    assert loaded.graph["filter"] == "pmid_count >= 2"
    assert loaded.number_of_edges() == 2


def test_export_view_writes_explicit_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(visualize_graph, "OUT", tmp_path)
    graph = nx.MultiDiGraph()
    graph.add_node("A", node_type="Cell")
    result = visualize_graph.export_view("graph_unfiltered", graph, "test", filter_predicate="unfiltered")
    metadata = json.loads((tmp_path / "graph_unfiltered" / "graph_unfiltered.metadata.json").read_text())
    assert result["filter"] == "unfiltered"
    assert metadata["source"]
    assert metadata["filter"] == "unfiltered"
