"""Tests for defect corpus Pydantic models."""

from __future__ import annotations

from figma_flutter_agent.defects.enums import BlastRadius, DefectOrigin, PipelineArrow
from figma_flutter_agent.defects.models import FamiliesDocument, FamilyEntry, OwnerRef


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
