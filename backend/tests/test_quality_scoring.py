from app.codex_pipeline import _assign_quality


def test_quality_scoring_keeps_named_uncertainties_and_context_completeness():
    result = _assign_quality(
        {
            "abstract": "A single-cell study in human tissue enrolled N=12 patients.",
            "publication_types": ["Journal Article"],
            "species": "human",
            "tissue": "lung",
            "cell_type": "airway epithelial cell",
        }
    )
    assert result["study_design"] == "single_cell"
    assert result["sample_size"] == 12
    assert any(p["name"] == "small_sample_size" for p in result["penalties"])
    assert result["context_completeness"]["tissue"] is True
    assert result["context_completeness"]["model"] is False


def test_quality_scoring_does_not_infer_missing_sample_size_or_replication():
    result = _assign_quality({"abstract": "A mechanism was observed.", "species": "unknown"})
    assert result["sample_size"] is None
    assert result["replication_status"] == "unknown"
    assert any(p["name"] == "sample_size_unknown" for p in result["penalties"])
