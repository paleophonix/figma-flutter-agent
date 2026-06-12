"""Translation-theory invariant gate (T1–T5)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.geometry.emit_invariants import validate_ast_coverage
from figma_flutter_agent.generator.geometry.invariants.models import (
    VIOLATION_SEVERITY,
    geometry_violation,
)
from figma_flutter_agent.generator.geometry.invariants.reporting import (
    mark_degraded_nodes,
    partition_geometry_violations,
    raise_on_hard_geometry_violations,
)
from figma_flutter_agent.generator.geometry.invariants.validate import (
    validate_geometry_invariants,
)
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    LayerClass,
    LayoutSlotIr,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
    TextMetricsFrame,
    WrapKind,
)


def _stack_with_children(*children: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=300.0, height=600.0),
        children=list(children),
    )


def test_t2_conservation_skips_stack() -> None:
    child = CleanDesignTreeNode(
        id="box",
        name="Box",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=100.0, height=50.0),
        stack_placement=StackPlacement(left=10.0, top=20.0, width=100.0, height=50.0),
    )
    stack = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=300.0, height=600.0),
        children=[child],
    )
    planned = plan_geometry_tree(stack)
    violations = validate_geometry_invariants(planned)
    assert not any(v.code.startswith("t2_") for v in violations)


def test_planned_tree_passes_invariants() -> None:
    child = CleanDesignTreeNode(
        id="box",
        name="Box",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=100.0, height=50.0),
        stack_placement=StackPlacement(left=10.0, top=20.0, width=100.0, height=50.0),
    )
    planned = plan_geometry_tree(_stack_with_children(child))
    violations = validate_geometry_invariants(planned, require_layout_slots=True)
    assert not violations


def test_t3_violation_when_delta_top_without_wrap() -> None:
    text = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        style=NodeStyle(font_size=16.0, line_height=1.5, glyph_top_offset=12.0),
        text_metrics_frame=TextMetricsFrame(
            font_size=16.0,
            strut_height_ratio=1.5,
            glyph_top_offset=12.0,
            delta_top=6.0,
            baseline_verifiable=True,
        ),
        layout_slot=LayoutSlotIr(layer_class=LayerClass.STATIC, wraps=()),
    )
    violations = validate_geometry_invariants(_stack_with_children(text))
    codes = {item.code for item in violations}
    assert "t3_baseline_delta" in codes


def test_t5_repaint_boundary_on_static_runs() -> None:
    static_bg = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.CONTAINER,
        stack_placement=StackPlacement(left=0.0, top=0.0, width=300.0, height=600.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=20.0, top=500.0, width=260.0, height=48.0),
    )
    deco = CleanDesignTreeNode(
        id="deco",
        name="Deco",
        type=NodeType.CONTAINER,
        stack_placement=StackPlacement(left=0.0, top=0.0, width=300.0, height=100.0),
    )
    planned = plan_geometry_tree(_stack_with_children(static_bg, button, deco))
    bg_slot = planned.children[0].layout_slot
    deco_slot = planned.children[2].layout_slot
    assert bg_slot is not None
    assert deco_slot is not None
    assert WrapKind.REPAINT_BOUNDARY in bg_slot.wraps
    assert WrapKind.REPAINT_BOUNDARY in deco_slot.wraps
    btn_slot = planned.children[1].layout_slot
    assert btn_slot is not None
    assert WrapKind.REPAINT_BOUNDARY not in btn_slot.wraps


def test_t3_passes_when_delta_top_wrap_present() -> None:
    text = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        text_metrics_frame=TextMetricsFrame(
            font_size=16.0,
            strut_height_ratio=1.5,
            glyph_top_offset=12.0,
            delta_top=6.0,
            baseline_verifiable=True,
        ),
        layout_slot=LayoutSlotIr(
            layer_class=LayerClass.STATIC,
            wraps=(WrapKind.DELTA_TOP_PADDING,),
        ),
    )
    violations = validate_geometry_invariants(_stack_with_children(text))
    assert not any(v.code == "t3_baseline_delta" for v in violations)


def test_inv_text_metrics_marks_input_baseline_gap_soft() -> None:
    hint = CleanDesignTreeNode(
        id="hint",
        name="Hint",
        type=NodeType.TEXT,
        style=NodeStyle(font_size=14.0, glyph_height=12.0, glyph_top_offset=4.0),
    )
    input_node = CleanDesignTreeNode(
        id="input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=280.0, height=56.0),
        children=[hint],
    )
    planned = plan_geometry_tree(_stack_with_children(input_node))
    violations = validate_geometry_invariants(planned)
    text_metrics = [item for item in violations if item.code == "inv_text_metrics"]

    assert text_metrics
    assert {item.severity for item in text_metrics} == {"soft"}
    hard, soft = partition_geometry_violations(violations)
    assert any(item.code == "inv_text_metrics" for item in soft)
    assert not any(item.code == "inv_text_metrics" for item in hard)


def test_soft_violation_does_not_raise() -> None:
    text = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        style=NodeStyle(font_size=16.0, line_height=1.5, glyph_top_offset=12.0),
        text_metrics_frame=TextMetricsFrame(
            font_size=16.0,
            strut_height_ratio=1.5,
            glyph_top_offset=12.0,
            delta_top=6.0,
            baseline_verifiable=True,
        ),
        layout_slot=LayoutSlotIr(layer_class=LayerClass.STATIC, wraps=()),
    )
    violations = validate_geometry_invariants(_stack_with_children(text))
    hard, soft = partition_geometry_violations(violations)
    assert soft
    assert not hard
    raise_on_hard_geometry_violations(violations, context="test")


def test_hard_violation_raises() -> None:
    slot = LayoutSlotIr(min_height=48.0, max_height=40.0)
    node = CleanDesignTreeNode(
        id="input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=280.0, height=40.0),
        layout_slot=slot,
    )
    violations = validate_geometry_invariants(_stack_with_children(node))
    hard, _ = partition_geometry_violations(violations)
    assert any(v.code == "constraint_normal" for v in hard)
    with pytest.raises(GenerationError, match="constraint_normal"):
        raise_on_hard_geometry_violations(violations, context="test")


def test_inv_ast_coverage_soft_by_default_hard_in_strict() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=300.0, height=600.0),
        layout_slot=LayoutSlotIr(layer_class=LayerClass.STATIC, wraps=()),
    )
    soft = validate_ast_coverage(root, "", sidecar_skipped=True, strict=False)
    assert len(soft) == 1
    assert soft[0].severity == "soft"
    hard = validate_ast_coverage(root, "", sidecar_skipped=True, strict=True)
    assert len(hard) == 1
    assert hard[0].severity == "hard"


def test_mark_degraded_nodes_sets_slot_flag() -> None:
    slot = LayoutSlotIr(layer_class=LayerClass.STATIC, wraps=())
    node = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        layout_slot=slot,
    )
    root = _stack_with_children(node)
    soft = [
        geometry_violation(
            code="t3_baseline_delta",
            node_id="label",
            detail="test",
        )
    ]
    updated = mark_degraded_nodes(root, soft)
    assert updated.children[0].layout_slot is not None
    assert updated.children[0].layout_slot.degraded is True


def test_violation_severity_map_covers_all_codes() -> None:
    geometry_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "figma_flutter_agent"
        / "generator"
        / "geometry"
    )
    codes: set[str] = set()
    for path in geometry_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        codes.update(re.findall(r'code="([^"]+)"', text))
    missing = sorted(
        code for code in codes if code not in VIOLATION_SEVERITY and code != "inv_ast_coverage"
    )
    assert not missing, f"Missing VIOLATION_SEVERITY entries: {missing}"
