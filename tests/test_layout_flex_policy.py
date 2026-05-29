"""Tests for Figma → Flutter flex wrap policy."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_flex_policy import (
    FlexWrapKind,
    apply_flex_wrap_to_widget,
    resolve_flex_wrap,
)
from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
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
