"""Artboard width clamp and mobile viewport alignment."""

from figma_flutter_agent.generator.artboard import clamp_oversized_frame_widths_to_artboard
from figma_flutter_agent.generator.layout.common import wrap_artboard_preview_layout_builder
from figma_flutter_agent.generator.layout.widgets import render_node_body
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
    assert "maxHeight: _artboardPreviewHeight" in wrapped


def test_artboard_preview_bounded_stack_skips_overflow_box() -> None:
    from figma_flutter_agent.generator.layout.common import artboard_preview_sized_box

    boxed = artboard_preview_sized_box(
        child="Stack(children: [])",
        alignment="Alignment.topLeft",
        bounded_child=True,
    )
    assert "OverflowBox(" not in boxed
    assert "height: previewH" in boxed


def test_mobile_stack_scroll_fallback_bounds_stack_height() -> None:
    """Live viewport scroll must not place a bare Stack inside SingleChildScrollView."""
    from figma_flutter_agent.generator.layout.widgets.position import (
        _wrap_root_stack_viewport,
    )

    tree = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=375.0, height=812.0),
        children=[
            CleanDesignTreeNode(
                id="1:text",
                name="Title",
                type=NodeType.TEXT,
                text="Title",
            ),
        ],
    )
    stack = "Stack(clipBehavior: Clip.none, children: [])"
    wrapped = _wrap_root_stack_viewport(
        tree,
        stack,
        is_layout_root=True,
        responsive_enabled=True,
    )
    assert "SingleChildScrollView(" in wrapped
    assert "FittedBox(" not in wrapped
    assert "constraints.maxWidth" in wrapped


def test_static_bottom_anchored_stack_uses_fixed_artboard_not_fittedbox() -> None:
    """Static mode must preserve Figma artboard height instead of viewport scale-down."""
    from figma_flutter_agent.generator.layout.widgets.position import (
        _wrap_root_stack_viewport,
    )

    tree = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="1:hero",
                name="Hero",
                type=NodeType.IMAGE,
                sizing=Sizing(width=414.0, height=300.0),
                stack_placement=StackPlacement(top=0.0, width=414.0, height=300.0),
            ),
            CleanDesignTreeNode(
                id="1:nav",
                name="Nav",
                type=NodeType.BOTTOM_NAV,
                sizing=Sizing(width=414.0, height=112.0),
                stack_placement=StackPlacement(
                    left=0.0,
                    bottom=0.0,
                    width=414.0,
                    height=112.0,
                ),
            ),
        ],
    )
    stack = "Stack(clipBehavior: Clip.none, children: [])"
    wrapped = _wrap_root_stack_viewport(
        tree,
        stack,
        is_layout_root=True,
        responsive_enabled=False,
    )
    assert "FittedBox(" not in wrapped
    assert "height: 896.0" in wrapped
    assert "viewportHeight" not in wrapped
    assert "SingleChildScrollView(" in wrapped


def test_static_plain_stack_wraps_scroll_viewport_without_unbound_local() -> None:
    """Non-bottom-anchored static stacks must wrap scroll viewport (no UnboundLocalError)."""
    from figma_flutter_agent.generator.layout.widgets.position import (
        _wrap_root_stack_viewport,
    )

    tree = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=375.0, height=812.0),
        children=[
            CleanDesignTreeNode(
                id="1:text",
                name="Title",
                type=NodeType.TEXT,
                text="Title",
            ),
        ],
    )
    stack = "Stack(clipBehavior: Clip.none, children: [])"
    wrapped = _wrap_root_stack_viewport(
        tree,
        stack,
        is_layout_root=True,
        responsive_enabled=False,
    )
    assert "SingleChildScrollView(" in wrapped
    assert "height: 812.0" in wrapped


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
    assert "maxHeight: double.infinity" not in body
