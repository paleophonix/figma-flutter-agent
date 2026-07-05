"""Tests for defect corpus Pydantic models."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError as PydanticValidationError

from figma_flutter_agent.defects.enums import BlastRadius, DefectOrigin, PipelineArrow
from figma_flutter_agent.defects.models import CaseMeta, FamiliesDocument, FamilyEntry, OwnerRef
from tests.defect_case_meta import case_timestamps


def test_family_entry_round_trip() -> None:
    family = FamilyEntry(
        id="llm_fidelity_authority_bypass",
        title="LLM fidelity authority bypass",
        pipeline_arrows=[PipelineArrow.A1],
        owning_stage="ir_validation",
        owners=[OwnerRef(module="src/foo.py", symbol="bar")],
        law_ids=["LAW-A1-FIDELITY-AUTHORITY"],
        default_blast_radius=BlastRadius.B2_SILENT_WRONG_BEHAVIOR,
        allowed_origins=[DefectOrigin.COMPILER],
        description="test",
        status="active",
    )
    doc = FamiliesDocument(version=1, families=[family])
    payload = doc.model_dump()
    restored = FamiliesDocument.model_validate(payload)
    assert restored.families[0].id == "llm_fidelity_authority_bypass"


def test_case_meta_requires_minute_precision_timestamps() -> None:
    observed = date(2026, 7, 5)
    created_at, updated_at = case_timestamps(observed, updated_hour=13)
    meta = CaseMeta(
        id="case-ts",
        title="t",
        project="synthetic",
        feature="f",
        observed_at=observed,
        created_at=created_at,
        updated_at=updated_at,
        summary="s",
    )
    assert meta.updated_at.hour == 13

    with pytest.raises(PydanticValidationError):
        CaseMeta(
            id="case-bad",
            title="t",
            project="synthetic",
            feature="f",
            observed_at=observed,
            created_at=created_at,
            updated_at=created_at.replace(minute=30, second=15),
            summary="s",
        )
