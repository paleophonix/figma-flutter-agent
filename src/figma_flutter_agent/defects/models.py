"""Pydantic models for defect corpus families and cases."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from figma_flutter_agent.defects.enums import (
    BlastRadius,
    Confidence,
    ContractCategory,
    DefectOrigin,
    DefectStatus,
    FieldClass,
    PipelineArrow,
)


class OwnerRef(BaseModel):
    """Owning compiler module and symbol."""

    model_config = ConfigDict(extra="forbid")

    module: str
    symbol: str


class FamilyEntry(BaseModel):
    """One defect family in ``families.yaml``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    pipeline_arrows: list[PipelineArrow]
    owning_stage: str
    owners: list[OwnerRef]
    law_ids: list[str]
    default_blast_radius: BlastRadius
    allowed_origins: list[DefectOrigin]
    description: str
    status: Literal["active", "deprecated"]


class FamiliesDocument(BaseModel):
    """Root document for ``families.yaml``."""

    model_config = ConfigDict(extra="forbid")

    version: int
    families: list[FamilyEntry]


class ContractRef(BaseModel):
    """Contract field classification for an occurrence."""

    model_config = ConfigDict(extra="forbid")

    field: str
    field_class: FieldClass
    category: ContractCategory
    expected: str
    actual: str


class EvidenceItem(BaseModel):
    """One evidence pointer for an occurrence."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["source_code", "test", "debug_artifact", "log"]
    path: str
    summary: str | None = None


class RepairRef(BaseModel):
    """Repair and regression proof for a FIXED occurrence."""

    model_config = ConfigDict(extra="forbid")

    summary: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    regression_tests: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)


class OccurrenceEntry(BaseModel):
    """One occurrence inside a case document."""

    model_config = ConfigDict(extra="forbid")

    id: str
    family_id: str
    pipeline_arrow: PipelineArrow
    law_id: str
    stage: str
    origin: DefectOrigin
    blast_radius: BlastRadius
    confidence: Confidence
    status: DefectStatus
    owner: OwnerRef
    contract: ContractRef
    authority_boundary: str | None = None
    loss_boundary: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    repair: RepairRef | None = None
    defer_reason: str | None = None
    missing_evidence: list[str] = Field(default_factory=list)


class CaseMeta(BaseModel):
    """Case header metadata."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    title: str
    project: str
    feature: str
    observed_at: date
    created_at: datetime
    updated_at: datetime
    summary: str
    case_kind: Literal["regression", "screen", "corpus"] | None = None

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def _minute_precision_utc(cls, value: datetime) -> datetime:
        """Require UTC (or naive-as-UTC) timestamps with minute precision."""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        if value.second or value.microsecond:
            msg = "timestamps must use minute precision (seconds and microseconds must be 0)"
            raise ValueError(msg)
        return value

    @field_validator("updated_at", mode="after")
    @classmethod
    def _updated_not_before_created(cls, value: datetime, info) -> datetime:
        """``updated_at`` must not precede ``created_at``."""
        created = info.data.get("created_at")
        if created is not None and value < created:
            msg = "updated_at must be greater than or equal to created_at"
            raise ValueError(msg)
        return value


class CaseDocument(BaseModel):
    """Root document for a case YAML file."""

    model_config = ConfigDict(extra="forbid")

    version: int
    case: CaseMeta
    occurrences: list[OccurrenceEntry]


class LoadedCorpus(BaseModel):
    """Families plus all case documents."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    families: FamiliesDocument
    cases: list[tuple[str, CaseDocument]]

    def family_by_id(self) -> dict[str, FamilyEntry]:
        """Index families by id."""
        return {family.id: family for family in self.families.families}
