"""E3-full: named degradation for VECTOR nodes with no resolvable asset (C.3)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.provenance import (
    DeviationReason,
    DeviationSeverity,
    activate_provenance_recorder,
    clear_provenance_recorder,
    write_provenance_dump,
)
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing
from figma_flutter_agent.schemas.geometry import StackPlacement


def _missing_vector_tree() -> CleanDesignTreeNode:
    vector = CleanDesignTreeNode(
        id="v1",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=8.0, height=8.0),
        style=NodeStyle(background_color="0xFF4285F4"),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=8.0, height=8.0),
    )
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        children=[vector],
    )


def test_missing_vector_emits_deviation_record(tmp_path: Path) -> None:
    """A VECTOR with no asset records a MISSING_VECTOR_ASSET deviation."""
    recorder = activate_provenance_recorder(feature_name="vector_leaf", project_dir=tmp_path)
    try:
        render_layout_file(_missing_vector_tree(), feature_name="vector_leaf", uses_svg=False)
        assert any(
            d.node_id == "v1" and d.reason == DeviationReason.MISSING_VECTOR_ASSET
            for d in recorder.deviations
        )
    finally:
        clear_provenance_recorder()


def test_missing_vector_does_not_emit_container_fallback(tmp_path: Path) -> None:
    """Production emit for a missing-asset VECTOR stays SizedBox.shrink(), not Container."""
    activate_provenance_recorder(feature_name="vector_leaf", project_dir=tmp_path)
    try:
        layout = render_layout_file(
            _missing_vector_tree(), feature_name="vector_leaf", uses_svg=False
        )["lib/generated/vector_leaf_layout.dart"]
    finally:
        clear_provenance_recorder()
    assert "SizedBox.shrink()" in layout


def test_preview_placeholder_layer_b_not_implemented() -> None:
    """Layer B (preview/debug placeholder) is explicitly out of scope for this slice.

    Per `docs/projects/codex-hardening/e3-full-vector-degradation-plan.md` (S4 decision),
    no generator-level debug/preview emit policy exists yet, so there is no separate
    placeholder path to assert here. This is intentionally documented as N/A rather
    than faked.
    """


def test_missing_vector_records_degraded_severity(tmp_path: Path) -> None:
    """The recorded deviation for a missing vector asset uses DEGRADED severity."""
    recorder = activate_provenance_recorder(feature_name="vector_leaf", project_dir=tmp_path)
    try:
        render_layout_file(_missing_vector_tree(), feature_name="vector_leaf", uses_svg=False)
        record = next(d for d in recorder.deviations if d.node_id == "v1")
        assert record.severity == DeviationSeverity.DEGRADED
    finally:
        clear_provenance_recorder()


def test_debug_report_contains_vector_degradation(tmp_path: Path) -> None:
    """The provenance dump payload exposes the missing-vector deviation."""
    activate_provenance_recorder(feature_name="vector_leaf", project_dir=tmp_path)
    try:
        render_layout_file(_missing_vector_tree(), feature_name="vector_leaf", uses_svg=False)
        path = write_provenance_dump()
        assert path is not None
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert any(
            d["nodeId"] == "v1" and d["reason"] == "missing_vector_asset"
            for d in payload["deviations"]
        )
    finally:
        clear_provenance_recorder()
