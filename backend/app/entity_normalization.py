"""Deterministic, non-speculative normalization for multidimensional targets."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedEntity:
    raw: str
    label: str
    entity_type: str
    status: str  # normalized | unresolved


# These are labels, not claims about database identity. External identifiers
# must be added only by a verified provider adapter in a later workstream.
_ALIASES: dict[str, tuple[str, str]] = {
    "il33": ("IL33", "gene"),
    "il-33": ("IL33", "gene"),
    "itepekimab": ("itepekimab", "drug"),
    "lung": ("lung", "tissue"),
    "airway epithelial cell": ("airway epithelial cell", "cell_type"),
    "airway epithelial cells": ("airway epithelial cell", "cell_type"),
}


def normalize_entity(raw: str, expected_type: str) -> NormalizedEntity:
    value = raw.strip()
    if not value:
        raise ValueError("entity values must not be empty")
    key = " ".join(value.casefold().split())
    alias = _ALIASES.get(key)
    if alias and alias[1] == expected_type:
        return NormalizedEntity(value, alias[0], expected_type, "normalized")
    return NormalizedEntity(value, value, expected_type, "unresolved")


def normalize_target_dimensions(values: list[str], expected_type: str) -> list[dict]:
    """Return auditable records while preserving unresolved input exactly."""
    result = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        entity = normalize_entity(value, expected_type)
        key = (entity.label, entity.entity_type)
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "raw": entity.raw,
            "label": entity.label,
            "entity_type": entity.entity_type,
            "status": entity.status,
        })
    return result
