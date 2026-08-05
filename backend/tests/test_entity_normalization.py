from app.entity_normalization import normalize_entity, normalize_target_dimensions


def test_known_alias_is_normalized_without_external_identity_claim():
    entity = normalize_entity(" IL-33 ", "gene")
    assert entity.label == "IL33"
    assert entity.status == "normalized"


def test_unknown_entity_is_preserved_as_unresolved():
    entity = normalize_entity("unlisted compound", "drug")
    assert entity.label == "unlisted compound"
    assert entity.status == "unresolved"


def test_dimension_normalization_deduplicates_canonical_labels():
    values = normalize_target_dimensions(["IL33", "il-33"], "gene")
    assert len(values) == 1
    assert values[0]["label"] == "IL33"
