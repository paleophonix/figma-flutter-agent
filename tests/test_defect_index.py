"""Tests for per-family defect corpus indexes."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from figma_flutter_agent.defects.enums import (
    BlastRadius,
    Confidence,
    ContractCategory,
    DefectOrigin,
    DefectStatus,
    FieldClass,
    PipelineArrow,
)
from figma_flutter_agent.defects.index import (
    build_family_indexes,
    check_family_indexes,
    write_family_indexes,
)
from figma_flutter_agent.defects.models import (
    CaseDocument,
    CaseMeta,
    ContractRef,
    FamiliesDocument,
    FamilyEntry,
    LoadedCorpus,
    OccurrenceEntry,
    OwnerRef,
)


def _family(family_id: str = "graph_sync_violation") -> FamilyEntry:
    return FamilyEntry(
        id=family_id,
        title="Graph sync violation",
        pipeline_arrows=[PipelineArrow.CP2],
        owning_stage="ir_pass",
        owners=[OwnerRef(module="src/foo.py", symbol="check_graph_sync")],
        law_ids=["LAW-CP2-GRAPH-SYNC"],
        default_blast_radius=BlastRadius.B3_BLOCKING,
        allowed_origins=[DefectOrigin.COMPILER],
        description="test",
        status="active",
    )


def _case(
    *,
    case_id: str = "case-a",
    family_id: str = "graph_sync_violation",
    status: DefectStatus = DefectStatus.OPEN,
    summary: str = "Line one.\n\nLine two.",
) -> CaseDocument:
    return CaseDocument(
        version=1,
        case=CaseMeta(
            id=case_id,
            title="Graph sync on screen",
            project="limbo",
            feature="food_menu",
            observed_at=date(2026, 7, 4),
            summary=summary,
        ),
        occurrences=[
            OccurrenceEntry(
                id="occ-a",
                family_id=family_id,
                pipeline_arrow=PipelineArrow.CP2,
                law_id="LAW-CP2-GRAPH-SYNC",
                stage="ir_pass",
                origin=DefectOrigin.COMPILER,
                blast_radius=BlastRadius.B3_BLOCKING,
                confidence=Confidence.HIGH,
                status=status,
                owner=OwnerRef(module="src/foo.py", symbol="check_graph_sync"),
                contract=ContractRef(
                    field="graph_sync",
                    field_class=FieldClass.COMPILER_OWNED,
                    category=ContractCategory.ILLEGAL,
                    expected="synced",
                    actual="broken",
                ),
                authority_boundary="conservation_checkpoint",
            ),
        ],
    )


def test_build_family_indexes_collapses_summary_and_groups_by_family() -> None:
    corpus = LoadedCorpus(
        families=FamiliesDocument(version=1, families=[_family(), _family("node_multiset_loss")]),
        cases=[
            ("corpus/cases/a.yaml", _case(summary="Alpha\n\nBeta")),
            (
                "corpus/cases/b.yaml",
                _case(case_id="case-b", family_id="node_multiset_loss"),
            ),
        ],
    )

    grouped = build_family_indexes(corpus)

    assert len(grouped["graph_sync_violation"]) == 1
    assert grouped["graph_sync_violation"][0].summary == "Alpha Beta"
    assert grouped["graph_sync_violation"][0].case_file == "cases/a.yaml"
    assert len(grouped["node_multiset_loss"]) == 1


def test_write_and_check_family_indexes(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    index_root = tmp_path / "index"
    cases_root.mkdir()
    corpus = LoadedCorpus(
        families=FamiliesDocument(version=1, families=[_family()]),
        cases=[("corpus/cases/case-a.yaml", _case())],
    )

    write_family_indexes(corpus, index_directory=index_root)
    assert (index_root / "graph_sync_violation.yaml").is_file()
    assert check_family_indexes(corpus, index_directory=index_root) == []

    stale = index_root / "graph_sync_violation.yaml"
    stale.write_text("version: 0\n", encoding="utf-8")
    errors = check_family_indexes(corpus, index_directory=index_root)
    assert any("out of date" in message for message in errors)


def test_write_family_indexes_removes_stale_family_file(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    index_root.mkdir()
    stale = index_root / "old_family.yaml"
    stale.write_text("version: 1\n", encoding="utf-8")

    corpus = LoadedCorpus(
        families=FamiliesDocument(version=1, families=[_family()]),
        cases=[("corpus/cases/case-a.yaml", _case())],
    )

    write_family_indexes(corpus, index_directory=index_root)

    assert not stale.is_file()
    assert (index_root / "graph_sync_violation.yaml").is_file()
