"""Tests for defect corpus cross-validation."""

from __future__ import annotations

from datetime import date

from figma_flutter_agent.defects.enums import (
    BlastRadius,
    Confidence,
    ContractCategory,
    DefectOrigin,
    DefectStatus,
    FieldClass,
    PipelineArrow,
)
from figma_flutter_agent.defects.models import (
    CaseDocument,
    CaseMeta,
    ContractRef,
    EvidenceItem,
    FamiliesDocument,
    FamilyEntry,
    LoadedCorpus,
    OccurrenceEntry,
    OwnerRef,
)
from figma_flutter_agent.defects.validation import ValidationError, validate_corpus


def _family() -> FamilyEntry:
    return FamilyEntry(
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


def test_unknown_family_reports_field_path() -> None:
    case = CaseDocument(
        version=1,
        case=CaseMeta(
            id="case-1",
            title="t",
            project="synthetic",
            feature="f",
            observed_at=date(2026, 7, 3),
            summary="s",
        ),
        occurrences=[
            OccurrenceEntry(
                id="occ-1",
                family_id="wrong_checkbox",
                pipeline_arrow=PipelineArrow.A1,
                law_id="LAW-X",
                stage="ir_validation",
                origin=DefectOrigin.COMPILER,
                blast_radius=BlastRadius.B2_SILENT_WRONG_BEHAVIOR,
                confidence=Confidence.HIGH,
                status=DefectStatus.OPEN,
                owner=OwnerRef(module="src/foo.py", symbol="bar"),
                contract=ContractRef(
                    field="fidelityTier",
                    field_class=FieldClass.COMPILER_OWNED,
                    category=ContractCategory.ILLEGAL,
                    expected="e",
                    actual="a",
                ),
                authority_boundary="fidelity_manifest",
            ),
        ],
    )
    errors = validate_corpus(
        LoadedCorpus(families=FamiliesDocument(version=1, families=[_family()]), cases=[("case.yaml", case)]),
    )
    assert len(errors) == 1
    assert errors[0].field_path == "case.occurrences[0].family_id"
    assert "unknown family" in errors[0].message


def test_fixed_requires_regression_proof() -> None:
    case = CaseDocument(
        version=1,
        case=CaseMeta(
            id="case-2",
            title="t",
            project="synthetic",
            feature="f",
            observed_at=date(2026, 7, 3),
            summary="s",
        ),
        occurrences=[
            OccurrenceEntry(
                id="occ-1",
                family_id="llm_fidelity_authority_bypass",
                pipeline_arrow=PipelineArrow.A1,
                law_id="LAW-A1-FIDELITY-AUTHORITY",
                stage="ir_validation",
                origin=DefectOrigin.COMPILER,
                blast_radius=BlastRadius.B2_SILENT_WRONG_BEHAVIOR,
                confidence=Confidence.HIGH,
                status=DefectStatus.FIXED,
                owner=OwnerRef(module="src/foo.py", symbol="bar"),
                contract=ContractRef(
                    field="fidelityTier",
                    field_class=FieldClass.COMPILER_OWNED,
                    category=ContractCategory.ILLEGAL,
                    expected="e",
                    actual="a",
                ),
                authority_boundary="fidelity_manifest",
                evidence=[
                    EvidenceItem(kind="source_code", path="src/foo.py", summary="s"),
                ],
            ),
        ],
    )
    errors = validate_corpus(
        LoadedCorpus(families=FamiliesDocument(version=1, families=[_family()]), cases=[("case.yaml", case)]),
    )
    field_paths = {error.field_path for error in errors}
    assert "case.occurrences[0].repair" in field_paths


def test_validation_error_format() -> None:
    error = ValidationError("corpus/cases/foo.yaml", "case.id", "duplicate")
    assert error.format() == "corpus/cases/foo.yaml:case.id: duplicate"
