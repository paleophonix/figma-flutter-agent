"""Artboard width clamp and mobile viewport alignment."""

from figma_flutter_agent.generator.artboard import clamp_oversized_frame_widths_to_artboard
from figma_flutter_agent.generator.layout.common import wrap_artboard_preview_layout_builder
from figma_flutter_agent.generator.layout.widgets.render import render_node_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_clamp_oversized_scroll_column_to_artboard_width() -> None:
    root = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:body",
                name="Body",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=391.0, height=626.8),
            ),
        ],
    )
    clamped = clamp_oversized_frame_widths_to_artboard(root)
    assert clamped.children[0].sizing.width == 390.0


def test_artboard_preview_layout_wraps_clip_rect() -> None:
    from figma_flutter_agent.generator.layout.common import artboard_preview_sized_box

    wrapped = wrap_artboard_preview_layout_builder(
        preview_child=artboard_preview_sized_box(child="child"),
        fallback="child",
    )
    assert "ClipRect(child: SizedBox(" in wrapped
    assert "OverflowBox(" in wrapped
    assert "maxHeight: double.infinity" in wrapped


def test_mobile_stack_viewport_aligns_top_left_without_preview_defines() -> None:
    tree = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:body",
                name="Body",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=700.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:text",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Title",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:nav",
                name="Nav",
                type=NodeType.BOTTOM_NAV,
                sizing=Sizing(width=390.0, height=138.0),
                stack_placement=StackPlacement(
                    left=0.0,
                    bottom=0.0,
                    width=390.0,
                    height=138.0,
                ),
            ),
        ],
    )
    body = render_node_body(tree, uses_svg=False, is_layout_root=True, responsive_enabled=True)
    assert "alignment: Alignment.topLeft" in body
    assert "alignment: Alignment.topCenter" not in body
