import pytest
from pydantic import ValidationError

from app.drug_knowledge import (
    DrugClaim,
    DrugRecord,
    Provenance,
    normalize_drug,
    normalize_drug_knowledge,
)


def test_unknown_drug_does_not_have_a_fabricated_identifier():
    drug = normalize_drug("unlisted compound")
    assert drug.status == "unresolved"
    assert drug.identifiers == []
    assert drug.provenance == []


def test_provider_adapter_preserves_source_identifiers_and_raw_payload():
    payload = {"name": "Compound X", "identifiers": [{"namespace": "chembl", "value": "CHEMBL1"}]}
    drug = normalize_drug(payload)
    assert drug.identifiers[0].value == "CHEMBL1"
    assert drug.raw == payload
    assert drug.identifiers[0].provenance.source_type == "provider"


def test_claim_requires_provenance_and_keeps_claim_types_separate():
    drug = DrugRecord(name="itepekimab", normalized_name="itepekimab", status="known")
    with pytest.raises(ValidationError):
        DrugClaim(drug=drug, predicate="efficacy", object="asthma", provenance=[])
    claim = DrugClaim(drug=drug, predicate="binds_target", object="IL33",
                      provenance=[Provenance(provider="DrugBank", source_type="canonical")])
    assert claim.predicate == "binds_target"
    assert claim.context.species.status == "unknown"


def test_knowledge_normalization_skips_unprovenanced_claims():
    result = normalize_drug_knowledge({"drug": {"name": "X"}, "claims": [
        {"predicate": "efficacy", "object": "disease"},
        {"predicate": "binds_target", "object": "T", "provenance": [
            {"provider": "curated", "source_type": "canonical"}
        ]},
    ]})
    assert len(result.claims) == 1
    assert result.claims[0].predicate == "binds_target"
