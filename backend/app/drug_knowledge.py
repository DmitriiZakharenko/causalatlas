"""Deterministic, provider-neutral drug knowledge contracts and adapters.

No function in this module performs I/O.  Adapters only normalize fields that
are present in provider payloads and never manufacture identifiers or claims.
"""
from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.context_models import StructuredContext, normalize_context


ResolutionStatus = Literal["known", "unknown", "unresolved"]
SourceType = Literal["canonical", "publication", "registry", "provider", "unknown"]
ClaimPredicate = Literal["binds_target", "indirectly_modulates", "associated_with_disease", "expression", "efficacy", "toxicity", "other"]


class Provenance(BaseModel):
    """Traceability for a value or claim; source IDs remain optional."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    source_type: SourceType = "unknown"
    source_id: str | None = None
    source_uri: str | None = None
    retrieved_at: str | None = None

    @field_validator("provider", "source_id", "source_uri", "retrieved_at", mode="before")
    @classmethod
    def _clean(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("provenance fields must be strings or null")
        value = value.strip()
        return value or None

    @field_validator("provider")
    @classmethod
    def _provider_required(cls, value: str) -> str:
        if not value:
            raise ValueError("provenance provider is required")
        return value


class DrugIdentifier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str
    value: str
    provenance: Provenance | None = None

    @field_validator("namespace", "value", mode="before")
    @classmethod
    def _required_text(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("identifier namespace and value must be non-empty")
        return value.strip()


class DrugRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    normalized_name: str | None = None
    status: ResolutionStatus = "unresolved"
    identifiers: list[DrugIdentifier] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    raw: dict[str, Any] | None = None

    @field_validator("name", "normalized_name", mode="before")
    @classmethod
    def _name_text(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("drug name must be non-empty")
        return value.strip()

    @model_validator(mode="after")
    def _state(self) -> "DrugRecord":
        if self.status == "unknown" and (self.name or self.identifiers):
            raise ValueError("unknown drugs cannot contain a name or identifier")
        if self.status == "known" and not (self.normalized_name or self.identifiers):
            raise ValueError("known drugs require a normalized name or identifier")
        return self

    @classmethod
    def unknown(cls, reason: str | None = None) -> "DrugRecord":
        # Keep a stable explicit object while avoiding an invented drug label.
        return cls.model_construct(name="", status="unknown", raw={"reason": reason} if reason else None)


class DrugClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drug: DrugRecord
    predicate: ClaimPredicate
    object: str
    provenance: list[Provenance] = Field(min_length=1)
    context: StructuredContext = Field(default_factory=StructuredContext)
    assertion_status: Literal["reported", "unknown"] = "reported"
    mechanism_class: Literal["direct_target", "indirect_pathway", "disease_association", "other"] = "other"

    @field_validator("object")
    @classmethod
    def _object_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("claim object must be non-empty")
        return value


class DrugKnowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drug: DrugRecord
    claims: list[DrugClaim] = Field(default_factory=list)
    provider_payload: dict[str, Any] | None = None


class DrugKnowledgeAdapter(Protocol):
    def normalize(self, payload: dict[str, Any]) -> DrugKnowledge: ...


def normalize_drug_record(payload: dict[str, Any], *, provider: str = "unknown") -> DrugRecord:
    """Convert a provider record without aliasing or inventing external IDs."""
    if not isinstance(payload, dict):
        raise TypeError("drug payload must be an object")
    name = payload.get("name", payload.get("drug_name"))
    if not isinstance(name, str) or not name.strip():
        return DrugRecord.model_construct(name="", status="unknown", raw=dict(payload))
    identifiers: list[DrugIdentifier] = []
    for item in payload.get("identifiers", []) or []:
        if isinstance(item, dict) and item.get("namespace") and item.get("value"):
            identifiers.append(DrugIdentifier(namespace=item["namespace"], value=item["value"],
                                               provenance=Provenance(provider=provider, source_type="provider")))
    provenance = [Provenance(provider=provider, source_type="provider")] if provider else []
    normalized = payload.get("normalized_name")
    status = payload.get("status", "known" if normalized or identifiers else "unresolved")
    if status not in {"known", "unknown", "unresolved"}:
        status = "unresolved"
    return DrugRecord(name=name, normalized_name=normalized, status=status, identifiers=identifiers,
                      provenance=provenance, raw=dict(payload))


def normalize_drug_knowledge(payload: dict[str, Any], *, provider: str = "unknown") -> DrugKnowledge:
    if not isinstance(payload, dict):
        raise TypeError("drug knowledge payload must be an object")
    drug = normalize_drug_record(payload.get("drug", payload), provider=provider)
    claims: list[DrugClaim] = []
    for item in payload.get("claims", []) or []:
        if not isinstance(item, dict) or not item.get("predicate") or not item.get("object"):
            continue
        claim_prov = [Provenance.model_validate(p) for p in item.get("provenance", []) if isinstance(p, dict)]
        if not claim_prov:
            continue
        claims.append(DrugClaim(drug=drug, predicate=item["predicate"], object=item["object"],
                                provenance=claim_prov, context=normalize_context(item.get("context"))))
    return DrugKnowledge(drug=drug, claims=claims, provider_payload=dict(payload))


def normalize_drug(value: str | dict[str, Any]) -> DrugRecord:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return DrugRecord.model_construct(name="", status="unknown")
        return DrugRecord(name=value, status="unresolved")
    return normalize_drug_record(value)
