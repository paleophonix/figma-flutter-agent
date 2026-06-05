"""Geometry calibration: flex deltas and INPUT padding (RC-5/RC-6)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.flex import (
    compute_flex_deltas,
    compute_input_metrics,
    min_input_height,
)
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
    WrapKind,
)


def _row(*children: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="row",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=300.0, height=48.0),
        children=list(children),
    )


def test_flex_child_fill_gets_expanded_wrap() -> None:
    child = CleanDesignTreeNode(
        id="fill",
        name="Fill",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FILL, width=100.0, height=40.0),
    )
    wraps, _ = compute_flex_deltas(_row(), child)
    assert WrapKind.EXPANDED in wraps


def test_input_fill_width_with_content_padding() -> None:
    hint = CleanDesignTreeNode(
        id="hint",
        name="Hint",
        type=NodeType.TEXT,
        style=NodeStyle(font_size=14.0, glyph_height=14.0, glyph_top_offset=8.0),
    )
    input_node = CleanDesignTreeNode(
        id="input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width_mode=SizingMode.FILL, width=280.0, height=56.0),
        children=[hint],
    )
    metrics = compute_input_metrics(input_node)
    assert metrics is not None
    assert metrics.input_padding_top is not None
    assert metrics.input_padding_bottom is not None
    assert min_input_height(56.0) >= 48.0


def test_flex_child_fill_not_pinned_to_aabb() -> None:
    child = CleanDesignTreeNode(
        id="fill",
        name="Fill",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FILL, height=40.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=280.0, height=40.0),
    )
    row = _row(child)
    planned = plan_geometry_tree(
        CleanDesignTreeNode(
            id="root",
            name="Screen",
            type=NodeType.STACK,
            sizing=Sizing(width=300.0, height=600.0),
            children=[row],
        )
    )
    planned_row = planned.children[0]
    planned_child = planned_row.children[0]
    slot = planned_child.layout_slot
    assert slot is not None
    assert WrapKind.EXPANDED in slot.wraps
    assert slot.slot_rect.width == 280.0 or slot.slot_rect.width == 0.0
