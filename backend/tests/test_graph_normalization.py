from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from build_graph import build_graph


def test_graph_merges_safe_within_role_aliases_but_preserves_gene_cytokine_roles():
    graph = build_graph(
        [
            {"source": "Itepekimab", "target": "IL-33", "relation": "suppresses", "source_type": "Drug", "target_type": "Cytokine", "pmid": "1"},
            {"source": "itepekimab", "target": "IL33", "relation": "suppresses", "source_type": "Drug", "target_type": "Cytokine", "pmid": "2"},
            {"source": "IL33", "target": "ILC2", "relation": "activates", "source_type": "Gene", "target_type": "Cell", "pmid": "3"},
        ]
    )
    node_ids = {node["id"] for node in graph["nodes"]}
    assert "itepekimab" in node_ids
    assert "Itepekimab" not in node_ids
    assert "IL-33" in node_ids
    assert "IL33" in node_ids
    assert next(edge for edge in graph["edges"] if edge["source"] == "itepekimab")["pmid_count"] == 2
    assert all(edge.get("relation") for edge in graph["edges"])
