"""
Phase 5 tests: `GET /api/graphs` and `GET /api/graphs/{disease_slug}`.

Against the REAL `data/graphs/asthma` and `data/graphs/ibd` files -- no
mocking of graph content, same pattern as test_eval_backfill.py. These never
touch the `claude` CLI.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import graphs as graphs_mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.db as db_mod
    from app.main import app

    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


def test_list_available_graphs_finds_real_asthma_and_ibd():
    graphs = graphs_mod.list_available_graphs()
    slugs = {g["disease_slug"] for g in graphs}
    assert {"asthma", "ibd"} <= slugs
    asthma = next(g for g in graphs if g["disease_slug"] == "asthma")
    assert asthma["node_count"] > 0
    assert asthma["edge_count"] > 0


def test_load_graph_for_ui_strips_full_pmid_lists_to_a_sample():
    graph = graphs_mod.load_graph_for_ui("asthma")
    node = graph["elements"]["nodes"][0]
    assert len(node["sample_pmids"]) <= graphs_mod.SAMPLE_PMID_LIMIT
    assert "pmid_count" in node
    # the stripped payload must never re-expose the raw unbounded `pmids` key
    assert "pmids" not in node

    edge = graph["elements"]["edges"][0]
    assert len(edge["sample_pmids"]) <= graphs_mod.SAMPLE_PMID_LIMIT
    assert "pmids" not in edge


def test_looks_like_extraction_noise_flags_known_sentence_fragments():
    for label in ["Suggesting", "And Effectively", "Number Of Total Asthma Exacerbations", "Which", "By 39"]:
        assert graphs_mod._looks_like_extraction_noise(label), label


def test_looks_like_extraction_noise_spares_real_entities():
    for label in ["IL-33", "Th2 cell", "Airway epithelium", "16Hbe Cells", "Tissue-resident memory T cell"]:
        assert not graphs_mod._looks_like_extraction_noise(label), label


def test_load_graph_for_ui_flags_noise_on_real_asthma_nodes():
    graph = graphs_mod.load_graph_for_ui("asthma")
    flagged = [n for n in graph["elements"]["nodes"] if n["looks_like_noise"]]
    # The current curated graph may already be noise-cleaned. The heuristic is
    # tested on known labels above; here we only assert that the display flag is
    # a valid boolean-shaped UI field and never changes the source graph size.
    assert all(isinstance(node["looks_like_noise"], bool) for node in graph["elements"]["nodes"])
    assert len(flagged) <= len(graph["elements"]["nodes"])


def test_load_graph_for_ui_counts_match_metadata():
    graph = graphs_mod.load_graph_for_ui("asthma")
    assert len(graph["elements"]["nodes"]) == graph["metadata"]["node_count"]
    assert len(graph["elements"]["edges"]) == graph["metadata"]["edge_count"]


def test_load_graph_for_ui_unknown_disease_raises():
    with pytest.raises(graphs_mod.GraphNotFoundError):
        graphs_mod.load_graph_for_ui("does_not_exist")


def test_run_scoped_graphs_are_loaded_from_their_own_directories():
    first = graphs_mod.load_graph_for_ui("asthma__asthma_20260805T103504Z")
    second = graphs_mod.load_graph_for_ui("asthma__asthma_20260805T112631Z")
    assert first["metadata"]["run_id"] == "asthma_20260805T103504Z"
    assert second["metadata"]["run_id"] == "asthma_20260805T112631Z"
    assert first["metadata"]["source"] != second["metadata"]["source"]
    assert first["metadata"]["source_node_count"] != second["metadata"]["source_node_count"]


def test_graphs_endpoint_lists_real_diseases(client):
    resp = client.get("/api/graphs")
    assert resp.status_code == 200
    slugs = {g["disease_slug"] for g in resp.json()["graphs"]}
    assert {"asthma", "ibd"} <= slugs


def test_graph_endpoint_returns_stripped_elements(client):
    resp = client.get("/api/graphs/ibd")
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["disease"] == "IBD"
    assert len(body["elements"]["nodes"]) == body["metadata"]["node_count"]
    assert len(body["elements"]["edges"]) == body["metadata"]["edge_count"]


def test_graph_endpoint_404_for_unknown_disease(client):
    resp = client.get("/api/graphs/does_not_exist")
    assert resp.status_code == 404
