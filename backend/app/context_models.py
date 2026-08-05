"""Provider-neutral, explicit experimental and biological context contracts.

These models describe the context attached to an observation.  They do not
assert that a label is biologically correct: an identifier is accepted only
when it was supplied by the caller or a verified provider.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ResolutionStatus = Literal["known", "unknown", "unresolved"]


class ContextValue(BaseModel):
    """One auditable context value, including an explicit missing state."""

    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    identifier: str | None = None
    status: ResolutionStatus = "unknown"
    raw: str | None = None
    reason: str | None = None

    @field_validator("value", "identifier", "raw", "reason", mode="before")
    @classmethod
    def _clean_text(cls, item: Any) -> Any:
        if item is None:
            return None
        if not isinstance(item, str):
            raise TypeError("context values must be strings or null")
        item = item.strip()
        return item or None

    def _validate_state(self) -> "ContextValue":
        if self.status == "known" and not (self.value or self.identifier):
            raise ValueError("known context values require value or identifier")
        if self.status == "unknown" and (self.value or self.identifier):
            raise ValueError("unknown context values cannot contain a resolved value")
        if self.status == "unresolved" and not (self.raw or self.value):
            raise ValueError("unresolved context values require raw input or value")
        return self

    def model_post_init(self, __context: Any) -> None:
        self._validate_state()

    @classmethod
    def unknown(cls, reason: str = "not provided") -> "ContextValue":
        return cls(status="unknown", reason=reason)

    @classmethod
    def unresolved(cls, raw: str, reason: str = "no verified mapping") -> "ContextValue":
        return cls(value=raw.strip(), raw=raw.strip(), status="unresolved", reason=reason)


ContextField = Literal["tissue", "cell_type", "species", "anatomical_compartment", "model", "assay"]


class StructuredContext(BaseModel):
    """Structured context shared by drug evidence and experimental records."""

    model_config = ConfigDict(extra="forbid")

    tissue: ContextValue = Field(default_factory=ContextValue.unknown)
    cell_type: ContextValue = Field(default_factory=ContextValue.unknown)
    species: ContextValue = Field(default_factory=ContextValue.unknown)
    anatomical_compartment: ContextValue = Field(default_factory=ContextValue.unknown)
    model: ContextValue = Field(default_factory=ContextValue.unknown)
    assay: ContextValue = Field(default_factory=ContextValue.unknown)

    @classmethod
    def from_raw(cls, values: dict[str, Any] | None = None) -> "StructuredContext":
        """Normalize supplied fields without resolving labels speculatively."""
        values = values or {}
        allowed = {"tissue", "cell_type", "species", "anatomical_compartment", "model", "assay"}
        unexpected = set(values) - allowed
        if unexpected:
            raise ValueError(f"unknown context fields: {', '.join(sorted(unexpected))}")
        fields: dict[str, Any] = {}
        for name in ("tissue", "cell_type", "species", "anatomical_compartment", "model", "assay"):
            item = values.get(name)
            if isinstance(item, ContextValue):
                fields[name] = item
            elif isinstance(item, str) and item.strip():
                fields[name] = ContextValue.unresolved(item)
            elif isinstance(item, dict):
                fields[name] = ContextValue.model_validate(item)
            elif item is not None:
                raise TypeError(f"{name} must be a string, object, or null")
        return cls(**fields)

    def supplied_fields(self) -> list[ContextField]:
        return [name for name in ("tissue", "cell_type", "species", "anatomical_compartment", "model", "assay")
                if getattr(self, name).status != "unknown"]


# Names used by callers that prefer the shorter domain term.
ExperimentalContext = StructuredContext
BiologicalContext = StructuredContext


def normalize_context(value: StructuredContext | dict[str, Any] | None) -> StructuredContext:
    if isinstance(value, StructuredContext):
        return value
    return StructuredContext.from_raw(value)
