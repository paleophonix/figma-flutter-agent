"""Typed semantic evidence models for IR provenance passes (no runtime recorder imports)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SemanticEvidenceSource(StrEnum):
    """Origin of a semantic signal before any production behavior may consume it."""

    TEXT_HINT = "text_hint"
    NAME_HINT = "name_hint"
    GEOMETRY = "geometry"
    COMPONENT_PROPERTY = "component_property"
    VISUAL_ANATOMY = "visual_anatomy"


class SemanticEvidenceAllowedEffect(StrEnum):
    """Maximum behavioral effect allowed for a semantic evidence item."""

    REPORT_ONLY = "report_only"
    CANDIDATE = "candidate"
    GATED_EMIT = "gated_emit"


class SemanticEvidenceLocaleScope(StrEnum):
    """Whether evidence depends on locale-sensitive copy."""

    GLOBAL = "global"
    LOCALE_DEPENDENT = "locale_dependent"


_EFFECT_RANK: dict[SemanticEvidenceAllowedEffect, int] = {
    SemanticEvidenceAllowedEffect.REPORT_ONLY: 0,
    SemanticEvidenceAllowedEffect.CANDIDATE: 1,
    SemanticEvidenceAllowedEffect.GATED_EMIT: 2,
}

_TEXT_NAME_SOURCES = frozenset(
    {
        SemanticEvidenceSource.TEXT_HINT,
        SemanticEvidenceSource.NAME_HINT,
    }
)


class SemanticEvidenceProvenance(BaseModel):
    """Trace data explaining how a semantic evidence item was produced."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    node_id: str = Field(alias="nodeId")
    rule: str
    input_values: dict[str, Any] = Field(default_factory=dict, alias="inputValues")
    source_field: str | None = Field(default=None, alias="sourceField")


class SemanticEvidence(BaseModel):
    """Typed semantic evidence; text/name hints may suggest but never decide."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source: SemanticEvidenceSource
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: SemanticEvidenceProvenance
    locale_scope: SemanticEvidenceLocaleScope = Field(alias="localeScope")
    allowed_effect: SemanticEvidenceAllowedEffect = Field(alias="allowedEffect")

    @model_validator(mode="after")
    def validate_allowed_effect_law(self) -> Self:
        """Fail fast when text/name evidence attempts to affect production directly."""
        if (
            self.source in _TEXT_NAME_SOURCES
            and _EFFECT_RANK[self.allowed_effect]
            > _EFFECT_RANK[SemanticEvidenceAllowedEffect.CANDIDATE]
        ):
            raise ValueError("text_hint/name_hint semantic evidence cannot exceed candidate")
        return self

    def to_payload(self) -> dict[str, Any]:
        """Serialize with stable camelCase keys for debug/report payloads."""
        return self.model_dump(mode="json", by_alias=True)


@dataclass(frozen=True)
class SemanticEvidencePolicy:
    """Explicit local gate contract for tests and future governance integration."""

    allow_gated_emit: bool = False

    def allows_production_effect(self, evidence: SemanticEvidence) -> bool:
        """Return True only when an explicit policy allows gated evidence to emit."""
        return (
            evidence.allowed_effect == SemanticEvidenceAllowedEffect.GATED_EMIT
            and self.allow_gated_emit
        )
