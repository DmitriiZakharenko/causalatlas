import pytest
from pydantic import ValidationError

from app.context_models import ContextValue, StructuredContext, normalize_context


def test_missing_context_is_explicitly_unknown():
    context = StructuredContext()
    assert context.tissue.status == "unknown"
    assert context.assay.reason == "not provided"
    assert context.supplied_fields() == []


def test_raw_context_is_unresolved_and_preserved():
    context = normalize_context({"tissue": "  ileum ", "species": {"value": "human", "status": "known"}})
    assert context.tissue.value == "ileum"
    assert context.tissue.raw == "ileum"
    assert context.tissue.status == "unresolved"
    assert context.species.status == "known"


def test_invalid_context_states_are_rejected():
    with pytest.raises(ValidationError):
        ContextValue(status="known")
    with pytest.raises(ValidationError):
        ContextValue(status="unknown", value="mouse")


def test_extra_context_fields_are_rejected():
    with pytest.raises(ValueError):
        StructuredContext.from_raw({"tissue": "lung", "organ": "lung"})
