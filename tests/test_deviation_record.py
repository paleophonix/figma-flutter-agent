"""DeviationRecord typed model tests (F2 — Foundation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.debug.provenance import (
    DeviationReason,
    DeviationSeverity,
    activate_provenance_recorder,
    clear_provenance_recorder,
    write_provenance_dump,
)
from figma_flutter_agent.generator.ir.passes.protocol import PassContext
from figma_flutter_agent.generator.ir.passes.provenance_record import record_deviation


def test_fact_mutation_requires_record(tmp_path: Path) -> None:
    """Mutating a fact must produce exactly one DeviationRecord."""
    recorder = activate_provenance_recorder(feature_name="demo_screen", project_dir=tmp_path)
    ctx = PassContext(screen_ir=None, clean_tree=None, provenance=recorder)  # type: ignore[arg-type]

    record_deviation(
        ctx,
        node_id="icon:1",
        field_name="type",
        before="VECTOR",
        after="ICON",
        reason=DeviationReason.STRUCTURAL_GROUPING_RECONCILE,
        source="reconcile.structural_grouping",
        severity=DeviationSeverity.RECOVERABLE,
    )

    assert len(recorder.deviations) == 1
    record = recorder.deviations[0]
    assert record.node_id == "icon:1"
    assert record.before == "VECTOR"
    assert record.after == "ICON"
    clear_provenance_recorder()


def test_no_call_means_no_record(tmp_path: Path) -> None:
    """No record means no mutation: an idle recorder has zero deviations."""
    recorder = activate_provenance_recorder(feature_name="demo_screen", project_dir=tmp_path)
    assert recorder.deviations == []
    clear_provenance_recorder()


def test_degraded_vector_record_serializes_to_debug_report(tmp_path: Path) -> None:
    """A degraded vector deviation is included in the provenance dump."""
    recorder = activate_provenance_recorder(feature_name="demo_screen", project_dir=tmp_path)
    ctx = PassContext(screen_ir=None, clean_tree=None, provenance=recorder)  # type: ignore[arg-type]

    record_deviation(
        ctx,
        node_id="vector:42",
        field_name="widget",
        before="Svg.asset",
        after="Container",
        reason=DeviationReason.MISSING_VECTOR_ASSET,
        source="svg.vector_degradation",
        severity=DeviationSeverity.DEGRADED,
        provenance={"assetKey": "icons/missing.svg"},
    )

    path = write_provenance_dump()
    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["deviations"] == [
        {
            "nodeId": "vector:42",
            "field": "widget",
            "before": "Svg.asset",
            "after": "Container",
            "reason": "missing_vector_asset",
            "source": "svg.vector_degradation",
            "severity": "degraded",
            "provenance": {"assetKey": "icons/missing.svg"},
        },
    ]
    clear_provenance_recorder()


def test_filesystem_recovery_record_uses_recoverable_severity(tmp_path: Path) -> None:
    """Filesystem-based composite icon recovery is recoverable, not degraded."""
    recorder = activate_provenance_recorder(feature_name="demo_screen", project_dir=tmp_path)
    ctx = PassContext(screen_ir=None, clean_tree=None, provenance=recorder)  # type: ignore[arg-type]

    record_deviation(
        ctx,
        node_id="icon:7",
        field_name="assetKey",
        before=None,
        after="icons/composite_7.svg",
        reason=DeviationReason.FILESYSTEM_COMPOSITE_ICON_RECOVERY,
        source="svg.filesystem_recovery",
        severity=DeviationSeverity.RECOVERABLE,
    )

    record = recorder.deviations[0]
    assert record.severity == DeviationSeverity.RECOVERABLE
    assert record.reason == DeviationReason.FILESYSTEM_COMPOSITE_ICON_RECOVERY
    clear_provenance_recorder()


def test_reason_enum_rejects_free_text_reasons() -> None:
    """The reason field only accepts DeviationReason members, not free text."""
    with pytest.raises(ValueError):
        DeviationReason("not_a_real_reason")
