from __future__ import annotations

from pathlib import Path

from app.codex_pipeline import PipelineContext, _materialize_local_drug_knowledge
from app.target_models import AnalysisTarget


def test_drug_layer_emits_gene_and_pathway_edges_from_one_supported_sentence(tmp_path):
    ctx = PipelineContext(
        "metformin_test",
        "type 2 diabetes",
        "PRKAA1",
        "let_it_rip",
        tmp_path / "session",
        tmp_path / "graph",
        AnalysisTarget(disease="type 2 diabetes", genes=["PRKAA1"], drugs=["metformin"]),
        "graph_only",
    )
    result = _materialize_local_drug_knowledge(
        ctx,
        [
            {
                "pmid": "123",
                "year": "2025",
                "species": "human",
                "abstract": "Metformin enhanced AMPK activation and increased PRKAA1 activity in type 2 diabetes.",
            }
        ],
    )
    targets = {(claim["edge"]["target"], claim["edge"]["target_type"]) for claim in result["claims"]}
    assert ("PRKAA1", "Gene") in targets
    assert ("AMPK", "Pathway") in targets
    assert all(claim["mechanism_class"] == "indirect_pathway" for claim in result["claims"])
