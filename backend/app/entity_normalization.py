"""Deterministic, non-speculative normalization for multidimensional targets."""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class NormalizedEntity:
    raw: str
    label: str
    entity_type: str
    status: str  # normalized | unresolved
    canonical_key: str = ""
    normalization_method: str = "unresolved"


# These are labels, not claims about database identity. External identifiers
# must be added only by a verified provider adapter in a later workstream.
_ALIASES: dict[str, tuple[str, str]] = {
    "il33": ("IL33", "gene"),
    "il-33": ("IL33", "gene"),
    "il 33": ("IL33", "gene"),
    "il 33 gene": ("IL33", "gene"),
    "itepekimab": ("itepekimab", "drug"),
    "itepekimab antibody": ("itepekimab", "drug"),
    "lung": ("lung", "tissue"),
    "lung tissue": ("lung", "tissue"),
    "pulmonary tissue": ("lung", "tissue"),
    "airway epithelial cell": ("airway epithelial cell", "cell_type"),
    "airway epithelial cells": ("airway epithelial cell", "cell_type"),
    "airway epithelium": ("airway epithelial cell", "cell_type"),
}


def canonical_key(value: str) -> str:
    """Return a comparison key without asserting an external database ID."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _clean_input(raw: str) -> str:
    return " ".join(raw.strip().split())


def normalize_entity(raw: str, expected_type: str) -> NormalizedEntity:
    value = _clean_input(raw)
    if not value:
        raise ValueError("entity values must not be empty")
    key = " ".join(value.casefold().split())
    alias = _ALIASES.get(key)
    if alias and alias[1] == expected_type:
        return NormalizedEntity(
            value,
            alias[0],
            expected_type,
            "normalized",
            canonical_key(alias[0]),
            "curated_alias",
        )
    return NormalizedEntity(value, value, expected_type, "unresolved", canonical_key(value), "preserved_input")


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
            "canonical_key": entity.canonical_key,
            "normalization_method": entity.normalization_method,
        })
    return result
