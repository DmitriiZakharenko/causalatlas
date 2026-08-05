import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from build_graph import build_graph, merge_graph, quality_gate_edges


def test_merge_preserves_parallel_claims_and_all_provenance():
    first = {
        "source": "A", "target": "B", "relation": "activates", "polarity": "positive",
        "pmid": "1", "session": "s1", "source_sentence": "one", "provenance_type": "pmid",
    }
    parallel = {
        "source": "A", "target": "B", "relation": "inhibits", "polarity": "negative",
        "pmids": ["2", "3"], "sessions": ["s2"],
        "source_refs": [{"canonical_id": "R-HSA-1"}], "provenance_type": "canonical_db",
    }
    graph = merge_graph(None, [first, parallel])
    assert len(graph["edges"]) == 2
    by_relation = {edge["primary_relation"]: edge for edge in graph["edges"]}
    assert by_relation["activates"]["pmids"] == ["1"]
    assert by_relation["activates"]["sessions"] == ["s1"]
    assert by_relation["activates"]["source_refs"][0]["source_sentence"] == "one"
    assert by_relation["inhibits"]["pmids"] == ["2", "3"]
    assert by_relation["inhibits"]["sessions"] == ["s2"]
    assert by_relation["inhibits"]["provenance_type"] == "canonical_db"


def test_legacy_edge_merge_does_not_drop_lists_or_claim_id():
    prior = {"edges": [{
        "claim_id": "claim_legacy", "source": "A", "target": "B",
        "relations": ["activates"], "pmids": ["1", "2"], "sessions": ["old", "older"],
        "source_refs": [{"pmid": "1", "source_sentence": "kept"}],
        "provenance_type": "pmid", "years": ["2020"], "species": ["human"],
        "confidence": 0.8, "context": {},
    }], "nodes": []}
    graph = merge_graph(prior, [{"source": "A", "target": "B", "relation": "activates", "pmid": "3"}])
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert edge["claim_id"] == "claim_legacy"
    assert edge["pmids"] == ["1", "2", "3"]
    assert edge["sessions"] == ["old", "older"]
    assert edge["source_refs"] == [{"pmid": "1", "source_sentence": "kept"}]


def test_claim_id_is_stable_for_same_claim():
    edge = {"source": "A", "target": "B", "relation": "activates", "pmid": "1", "context": {"disease": ["x"]}}
    assert build_graph([edge])["edges"][0]["claim_id"] == build_graph([edge])["edges"][0]["claim_id"]


def test_quality_gate_rejects_sentence_free_unknown_claims():
    accepted, rejected = quality_gate_edges(
        [
            {
                "source": "IL-33",
                "target": "ILC2",
                "source_type": "Cytokine",
                "target_type": "Cell",
                "relation": "activates",
                "pmid": "123",
                "provenance_type": "pmid",
                "source_sentence": "IL-33 activates ILC2 cells in asthma.",
            },
            {
                "source": "TNF",
                "target": "Unknown fragment",
                "source_type": "unknown",
                "target_type": "unknown",
                "relation": "activates",
                "pmid": "456",
                "provenance_type": "unknown",
            },
        ],
        target={"disease": "asthma", "genes": ["IL33"]},
        publications=[{"pmid": "123", "title": "IL-33 in asthma", "abstract": "IL-33 activates ILC2 cells in asthma."}],
    )

    assert len(accepted) == 1
    assert rejected[0]["reasons"] == ["missing_source_sentence", "unknown_node_type", "non_pmid_provenance", "target_relevance_not_demonstrated"]
