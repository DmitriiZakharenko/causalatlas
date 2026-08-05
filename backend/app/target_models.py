"""Versioned, backward-compatible analysis target contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.entity_normalization import normalize_target_dimensions


TargetSchemaVersion = Literal["target.v1"]


class StatisticalCandidate(BaseModel):
    """Optional external statistical signal; never treated as literature evidence."""

    model_config = ConfigDict(extra="forbid")

    drug: str
    gene: str
    method: str
    effect: float | None = None
    p_value: float | None = None
    q_value: float | None = None
    source: str
    source_id: str | None = None


class AnalysisTarget(BaseModel):
    """Resolved target used by the pipeline and persisted with every new run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: TargetSchemaVersion = "target.v1"
    disease: str | None = None
    genes: list[str] = Field(default_factory=list)
    drugs: list[str] = Field(default_factory=list)
    tissues: list[str] = Field(default_factory=list)
    cell_types: list[str] = Field(default_factory=list)
    statistical_candidates: list[StatisticalCandidate] = Field(default_factory=list)
    query_mode: str | None = None

    @field_validator("disease", "genes", "drugs", "tissues", "cell_types", mode="before")
    @classmethod
    def _strip_values(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return value

    @field_validator("genes", "drugs", "tissues", "cell_types")
    @classmethod
    def _deduplicate_values(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def _validate_target(self) -> "AnalysisTarget":
        if not self.disease and not (self.genes and self.drugs):
            raise ValueError("disease is required unless both genes and drugs are provided")
        if self.query_mode is None:
            dimensions = sum(bool(values) for values in (self.genes, self.drugs, self.tissues, self.cell_types))
            self.query_mode = "disease" if dimensions == 0 else "multidimensional"
        return self


class AnalysisTargetRequest(BaseModel):
    """Accepts the new nested target plus legacy top-level disease/gene fields."""

    model_config = ConfigDict(extra="forbid")

    disease: str | None = None
    gene: str | None = None
    target: AnalysisTarget | None = None

    @model_validator(mode="after")
    def _resolve(self) -> "AnalysisTargetRequest":
        legacy_disease = self.disease.strip() if isinstance(self.disease, str) else self.disease
        legacy_gene = self.gene.strip() if isinstance(self.gene, str) else self.gene
        if self.target is not None:
            if legacy_disease and legacy_disease != self.target.disease:
                raise ValueError("disease conflicts with target.disease")
            if legacy_gene and self.target.genes and [legacy_gene] != self.target.genes:
                raise ValueError("gene conflicts with target.genes")
            return self
        if not legacy_disease:
            raise ValueError("disease is required")
        self.disease = legacy_disease
        self.gene = legacy_gene or None
        self.target = AnalysisTarget(disease=legacy_disease, genes=[legacy_gene] if legacy_gene else [])
        return self

    def resolved_target(self) -> AnalysisTarget:
        assert self.target is not None
        return self.target

    def normalized_dimensions(self) -> dict[str, list[dict]]:
        target = self.resolved_target()
        return {
            "genes": normalize_target_dimensions(target.genes, "gene"),
            "drugs": normalize_target_dimensions(target.drugs, "drug"),
            "tissues": normalize_target_dimensions(target.tissues, "tissue"),
            "cell_types": normalize_target_dimensions(target.cell_types, "cell_type"),
        }
