from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.target_models import AnalysisTargetRequest


def test_legacy_request_normalizes_to_versioned_target():
    request = AnalysisTargetRequest(disease=" asthma ", gene=" IL33 ")
    assert request.resolved_target().model_dump(mode="json") == {
        "schema_version": "target.v1",
        "disease": "asthma",
        "genes": ["IL33"],
        "drugs": [],
        "tissues": [],
            "cell_types": [],
            "statistical_candidates": [],
            "query_mode": "multidimensional",
    }


def test_nested_target_deduplicates_and_strips_values():
    request = AnalysisTargetRequest(
        target={
            "disease": "asthma",
            "genes": ["IL33", " IL33 "],
            "drugs": ["itepekimab"],
            "tissues": ["lung"],
            "cell_types": ["airway epithelial cell"],
        }
    )
    target = request.resolved_target()
    assert target.genes == ["IL33"]
    assert target.query_mode == "multidimensional"


def test_conflicting_legacy_and_nested_values_are_rejected():
    with pytest.raises(ValidationError, match="conflicts"):
        AnalysisTargetRequest(
            disease="asthma",
            gene="IL33",
            target={"disease": "asthma", "genes": ["IL11"]},
        )


def test_unknown_request_fields_are_rejected_instead_of_dropped():
    with pytest.raises(ValidationError):
        AnalysisTargetRequest(disease="asthma", tissue="lung")
