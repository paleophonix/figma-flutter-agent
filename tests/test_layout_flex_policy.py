"""Tests for Figma → Flutter flex wrap policy."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_flex_policy import (
    FlexWrapKind,
    apply_flex_wrap_to_widget,
    resolve_cross_axis_alignment,
    resolve_flex_wrap,
    wrap_column_child_width_fill,
)
from figma_flutter_agent.schemas import Alignment
from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_row_fill_child_gets_expanded() -> None:
    node = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hi",
        sizing=Sizing(width_mode=SizingMode.FILL),
    )
    assert (
        resolve_flex_wrap(parent_type=NodeType.ROW, node=node) == FlexWrapKind.EXPANDED
    )


def test_row_fixed_text_gets_flexible_loose() -> None:
    node = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hi",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=120.0),
    )
    assert (
        resolve_flex_wrap(parent_type=NodeType.ROW, node=node)
        == FlexWrapKind.FLEXIBLE_LOOSE
    )


def test_row_fixed_text_renders_flexible_in_layout() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hello",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=100.0),
    )
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=400.0),
        children=[child],
    )
    layout = render_layout_file(row, feature_name="flex_row", uses_svg=False)[
        "lib/generated/flex_row_layout.dart"
    ]
    assert "Flexible(fit: FlexFit.loose" in layout


def test_column_stack_child_gets_bounded_sized_box() -> None:
    back = CleanDesignTreeNode(
        id="42:3733",
        name="arrow-narrow-left",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=24.0, height=24.0),
        children=[],
    )
    column = CleanDesignTreeNode(
        id="42:3215",
        name="Content",
        type=NodeType.COLUMN,
        sizing=Sizing(width=327.0, height=511.0),
        children=[back],
    )
    layout = render_layout_file(column, feature_name="content_col", uses_svg=False)[
        "lib/generated/content_col_layout.dart"
    ]
    assert "SizedBox(width: 24.0, height: 24.0, child: Stack(" in layout


def test_apply_flex_wrap_expanded_expression() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="X",
        type=NodeType.TEXT,
        text="A",
        sizing=Sizing(width_mode=SizingMode.FILL),
    )
    wrapped = apply_flex_wrap_to_widget(
        "Text('A')",
        parent_type=NodeType.ROW,
        node=node,
    )
    assert wrapped == "Expanded(child: Text('A'))"


def test_column_width_fill_row_with_height_gets_bounded_sized_box() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL, height=48.0),
        children=[],
    )
    wrapped = apply_flex_wrap_to_widget(
        "Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [])",
        parent_type=NodeType.COLUMN,
        node=row,
    )
    assert "SizedBox(width: double.infinity, height: 48.0, child: Row(" in wrapped


def test_row_cross_stretch_relaxes_under_parent_row() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Inner",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL),
        children=[],
    )
    cross = resolve_cross_axis_alignment(
        row,
        parent_type=NodeType.ROW,
        cross="stretch",
    )
    assert cross == "CrossAxisAlignment.start"


def test_row_cross_stretch_kept_under_column_with_pixel_height() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Bar",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL, height=48.0),
        children=[],
    )
    cross = resolve_cross_axis_alignment(
        row,
        parent_type=NodeType.COLUMN,
        cross="stretch",
    )
    assert cross == "CrossAxisAlignment.stretch"


def test_row_cross_stretch_relaxed_for_title_toolbar() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Header",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Title",
                type=NodeType.COLUMN,
                children=[
                    CleanDesignTreeNode(
                        id="3",
                        name="Label",
                        type=NodeType.TEXT,
                        text="Личные данные",
                    )
                ],
            )
        ],
    )
    cross = resolve_cross_axis_alignment(
        row,
        parent_type=NodeType.COLUMN,
        cross="stretch",
    )
    assert cross == "CrossAxisAlignment.start"


def test_form_field_group_omits_fixed_height_on_width_fill() -> None:
    field = CleanDesignTreeNode(
        id="1",
        name="Field",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, height=84.0),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Label",
                type=NodeType.TEXT,
                text="ФИО",
            ),
            CleanDesignTreeNode(
                id="3",
                name="Input",
                type=NodeType.INPUT,
                sizing=Sizing(width=317.0, height=52.0),
            ),
        ],
    )
    wrapped = wrap_column_child_width_fill("Column(children: [])", field)
    assert "height: 84.0" not in wrapped
    assert wrapped.startswith("SizedBox(width: double.infinity, child:")


def test_column_with_cross_stretch_expands_under_row() -> None:
    title = CleanDesignTreeNode(
        id="2",
        name="Title",
        type=NodeType.TEXT,
        text="Hello",
        sizing=Sizing(width_mode=SizingMode.FILL),
    )
    column = CleanDesignTreeNode(
        id="1",
        name="Labels",
        type=NodeType.COLUMN,
        alignment=Alignment(cross="stretch"),
        children=[title],
    )
    assert resolve_flex_wrap(parent_type=NodeType.ROW, node=column) == FlexWrapKind.EXPANDED


def test_nested_row_with_flexible_child_expands_under_parent_row() -> None:
    label = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Title",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=120.0),
    )
    inner = CleanDesignTreeNode(
        id="1",
        name="Inner",
        type=NodeType.ROW,
        children=[label],
    )
    assert resolve_flex_wrap(parent_type=NodeType.ROW, node=inner) == FlexWrapKind.EXPANDED
    wrapped = apply_flex_wrap_to_widget(
        "Row(children: [])",
        parent_type=NodeType.ROW,
        node=inner,
    )
    assert wrapped.startswith("Expanded(child: Row(")


def test_column_width_fill_row_without_height_relaxes_cross_stretch() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL),
        children=[],
    )
    wrapped = apply_flex_wrap_to_widget(
        "Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [])",
        parent_type=NodeType.COLUMN,
        node=row,
    )
    assert "CrossAxisAlignment.stretch" not in wrapped
    assert "SizedBox(width: double.infinity, child: Row(" in wrapped


def test_wrap_column_child_width_fill_is_shared_helper() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, height=12.0),
    )
    assert wrap_column_child_width_fill("Row(children: [])", node).startswith(
        "SizedBox(width: double.infinity, height: 12.0"
    )


def test_row_fill_width_and_height_does_not_wrap_expanded_in_sized_box() -> None:
    """ROW child with FILL on both axes must not become SizedBox → Expanded."""
    from figma_flutter_agent.generator.layout_widget import _wrap_sizing

    node = CleanDesignTreeNode(
        id="611:1338",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FILL,
            width=336.5,
            height=56.0,
        ),
    )
    wrapped = _wrap_sizing(
        node,
        "Semantics(label: 'Save', child: Text('Save'))",
        parent_type=NodeType.ROW,
    )
    assert "SizedBox(height: double.infinity, child: Expanded" not in wrapped
    assert wrapped.startswith("Expanded(")
