"""Translation-theory invariant gate (T1–T5)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry_invariants import validate_geometry_invariants
from figma_flutter_agent.generator.geometry_planner import plan_geometry_tree
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
