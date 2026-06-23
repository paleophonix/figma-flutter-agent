"""Flex emitter constraint satisfaction: prevent RenderFlex overflow."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
)


def _expected_overflow_gap_literal(
    *,
    row_width: float,
    child_total: float,
    n_gaps: int,
    safety_total: float = 0.5,
) -> str:
    """Mirror emitter overflow gap sizing including geometry literal rounding."""
    available_gap = max(0.0, row_width - child_total)
    safety_per_gap = safety_total / n_gaps if n_gaps > 0 else 0.0
    scaled_gap = max(0.0, available_gap / n_gaps - safety_per_gap) if n_gaps > 0 else 0.0
    return format_geometry_literal(scaled_gap)


def test_row_spacing_replaced_when_two_children_overflow() -> None:
    row = CleanDesignTreeNode(
        id="1:row",
        name="TitleRow",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=327.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:left",
                name="Left",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=155.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id="1:right",
                name="Right",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=157.5, height=18.0),
            ),
        ],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "spacing: 16.0" not in compact
    gap_lit = _expected_overflow_gap_literal(
        row_width=327.0,
        child_total=312.5,
        n_gaps=1,
    )
    assert f"SizedBox(width: {gap_lit})" in compact


def test_three_child_row_overflow_distributes_gaps() -> None:
    row = CleanDesignTreeNode(
        id="1:row",
        name="Chips",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=327.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:a",
                name="A",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=100.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id="1:b",
                name="B",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=100.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id="1:c",
                name="C",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=100.0, height=18.0),
            ),
        ],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "spacing: 16.0" not in compact
    gap_lit = _expected_overflow_gap_literal(
        row_width=327.0,
        child_total=300.0,
        n_gaps=2,
    )
    assert f"SizedBox(width: {gap_lit})" in compact


def test_hug_row_overflow_uses_parent_column_width() -> None:
    parent = CleanDesignTreeNode(
        id="1:col",
        name="Content",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=327.0),
        children=[],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="TitleRow",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(height=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:left",
                name="Left",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=155.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id="1:right",
                name="Right",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=157.5, height=18.0),
            ),
        ],
    )
    body = render_node_body(
        row,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
        parent_node=parent,
    )
    compact = body.replace("\n", "")
    assert "spacing: 16.0" not in compact
    gap_lit = _expected_overflow_gap_literal(
        row_width=327.0,
        child_total=312.5,
        n_gaps=1,
    )
    assert f"SizedBox(width: {gap_lit})" in compact


def test_divider_row_with_center_text_compresses_gaps_for_runtime_drift() -> None:
    row = CleanDesignTreeNode(
        id="28:4023",
        name="or",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=327.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="28:4024",
                name="Line",
                type=NodeType.VECTOR,
                sizing=Sizing(width_mode=SizingMode.FILL, width=140.5, height=1.0),
            ),
            CleanDesignTreeNode(
                id="28:4025",
                name="Or",
                type=NodeType.TEXT,
                text="Or",
                sizing=Sizing(width=14.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id="28:4026",
                name="Line",
                type=NodeType.VECTOR,
                sizing=Sizing(width_mode=SizingMode.FILL, width=140.5, height=1.0),
            ),
        ],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "spacing: 16.0" not in compact
    gap_lit = _expected_overflow_gap_literal(
        row_width=327.0,
        child_total=295.0,
        n_gaps=2,
    )
    assert f"SizedBox(width: {gap_lit})" in compact


def test_row_rigid_overflow_uses_parent_column_when_row_is_hug() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        row_rigid_main_axis_overflow,
    )

    parent = CleanDesignTreeNode(
        id="1:col",
        name="Content",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=327.0),
        children=[],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="TitleRow",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(height=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:left",
                name="Left",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=155.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id="1:right",
                name="Right",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=157.5, height=18.0),
            ),
        ],
    )
    assert row_rigid_main_axis_overflow(row) == 0.0
    assert row_rigid_main_axis_overflow(row, parent_node=parent) > 0.0


def test_unmeasurable_row_wraps_fitted_box() -> None:
    row = CleanDesignTreeNode(
        id="1:row",
        name="Unknown",
        type=NodeType.ROW,
        spacing=12.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=200.0, height=24.0),
        children=[
            CleanDesignTreeNode(id="1:a", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="1:b", name="B", type=NodeType.TEXT, text="B"),
        ],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "FittedBox(fit: BoxFit.scaleDown" in compact
