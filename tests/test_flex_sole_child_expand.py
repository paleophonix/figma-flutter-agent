"""Sole undersized HUG/FIXED children in FILL rows expand to parent span."""

from figma_flutter_agent.generator.geometry.flex import compute_flex_deltas
from figma_flutter_agent.generator.layout.flex_policy import FlexWrapKind, resolve_flex_wrap
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    WrapKind,
)


def test_sole_undersized_fixed_child_resolves_to_expanded() -> None:
    inner = CleanDesignTreeNode(
        id="1:inner",
        name="Inner",
        type=NodeType.ROW,
        spacing=12.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=191.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:back",
                name="Back",
                type=NodeType.BUTTON,
                sizing=Sizing(width=48.0, height=48.0),
            ),
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Personal data title",
                sizing=Sizing(width_mode=SizingMode.FILL, width=131.0, height=26.0),
                style=NodeStyle(font_size=17.0, font_weight="w800"),
            ),
        ],
    )
    outer = CleanDesignTreeNode(
        id="1:outer",
        name="Outer",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=357.0, height=48.0),
        children=[inner],
    )
    kind = resolve_flex_wrap(
        parent_type=NodeType.ROW,
        node=inner,
        parent_node=outer,
    )
    assert kind == FlexWrapKind.EXPANDED
    wraps, _ = compute_flex_deltas(outer, inner)
    assert WrapKind.EXPANDED in wraps
    assert WrapKind.CONSTRAINED_BOX not in wraps
    assert WrapKind.FLEXIBLE_LOOSE not in wraps


def test_sole_undersized_group_emits_expanded_without_width_cap() -> None:
    inner = CleanDesignTreeNode(
        id="1:inner",
        name="Inner",
        type=NodeType.ROW,
        spacing=12.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=191.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:back",
                name="Back",
                type=NodeType.BUTTON,
                sizing=Sizing(width=48.0, height=48.0),
            ),
            CleanDesignTreeNode(
                id="1:title",
                name="TitleCol",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=131.0, height=26.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:text",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Personal data title",
                        style=NodeStyle(font_size=17.0, font_weight="w800"),
                    )
                ],
            ),
        ],
    )
    outer = CleanDesignTreeNode(
        id="1:outer",
        name="Outer",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=357.0, height=48.0),
        children=[inner],
    )
    body = render_node_body(outer, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Expanded(child:" in compact
    assert "SizedBox(width: 191.0, child: Row(" not in compact
