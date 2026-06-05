"""Elastic bounds and flex reconcile parent gate (WP-2)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.baseline import flutter_baseline_offset
from figma_flutter_agent.generator.geometry.flex import compute_flex_deltas
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.generator.layout.flex_reconcile import apply_flex_guards_from_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    HeightFit,
    LayoutBackend,
    LayoutSlotIr,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
    WrapKind,
)


def _column(*children: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="col",
        name="Column",
        type=NodeType.COLUMN,
        sizing=Sizing(width=300.0, height=400.0),
        children=list(children),
    )


def test_input_fill_width_in_column_is_stretch_not_expanded() -> None:
    input_node = CleanDesignTreeNode(
        id="input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width_mode=SizingMode.FILL, width=280.0, height=48.0),
    )
    wraps, _ = compute_flex_deltas(_column(), input_node)
    assert WrapKind.EXPANDED not in wraps
    assert WrapKind.CROSS_STRETCH_WIDTH in wraps


def test_elastic_bounds_a11y() -> None:
    input_node = CleanDesignTreeNode(
        id="input",
        name="Email",
        type=NodeType.INPUT,
        sizing=Sizing(width=280.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="hint",
                name="Hint",
                type=NodeType.TEXT,
                style=NodeStyle(font_size=14.0, glyph_height=14.0, glyph_top_offset=8.0),
            )
        ],
    )
    planned = plan_geometry_tree(_column(input_node))
    slot = planned.children[0].layout_slot
    assert slot is not None
    assert slot.height_fit == HeightFit.MIN
    assert slot.min_height is not None and slot.min_height >= 48.0


def test_flex_reconcile_respects_parent_stack() -> None:
    child = CleanDesignTreeNode(
        id="abs",
        name="Abs",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=100.0, height=40.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=100.0, height=40.0),
        layout_slot=LayoutSlotIr(backend=LayoutBackend.STACK),
    )
    stack = CleanDesignTreeNode(
        id="stack",
        name="Stack",
        type=NodeType.STACK,
        sizing=Sizing(width=300.0, height=300.0),
        layout_slot=LayoutSlotIr(backend=LayoutBackend.STACK),
        children=[child],
    )
    source = "class Demo { Widget build() => Container(key: const ValueKey('figma-abs')); }"
    assert apply_flex_guards_from_tree(source, stack) == source


def test_baseline_oracle_fallback() -> None:
    assert flutter_baseline_offset(16.0) == 16.0 * 0.72
    assert flutter_baseline_offset(16.0, font_family="Roboto") == 16.0 * 0.72
