"""Tall phone column artboards scroll in browser viewports."""

from figma_flutter_agent.generator.artboard import is_tall_mobile_artboard
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_is_tall_mobile_artboard_detects_extra_tall_frames() -> None:
    assert is_tall_mobile_artboard(390.0, 917.3) is True
    assert is_tall_mobile_artboard(390.0, 844.0) is False
    assert is_tall_mobile_artboard(600.0, 1200.0) is False


def test_short_column_static_root_bounds_artboard_without_defines() -> None:
    root = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:text",
                name="Title",
                type=NodeType.TEXT,
                text="Hello",
            )
        ],
    )
    layout = render_layout_file(
        root,
        feature_name="short_column_static",
        uses_svg=False,
        responsive_enabled=False,
    )["lib/generated/short_column_static_layout.dart"]
    assert "_artboardPreviewWidth" in layout
    assert "SizedBox(width: 390.0, height: 844.0" in layout
    assert "constraints.maxWidth" not in layout


def test_tall_column_root_emits_scroll_with_artboard_preview() -> None:
    root = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=917.0),
        children=[
            CleanDesignTreeNode(
                id="1:body",
                name="Body",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=893.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:text",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Chats",
                    )
                ],
            )
        ],
    )
    layout = render_layout_file(
        root,
        feature_name="tall_column",
        uses_svg=False,
        responsive_enabled=True,
    )["lib/generated/tall_column_layout.dart"]
    assert "_artboardPreviewWidth" in layout
    assert "SingleChildScrollView(" in layout
    compact = layout.replace(" ", "")
    assert "SizedBox(width:constraints.maxWidth" in compact
    assert "constraints.maxWidth < 390" not in layout
    assert "MediaQuery.sizeOf(context).height" in layout
    assert "OverflowBox(" in layout
    assert "maxHeight: _artboardPreviewHeight" in layout


def test_tall_screen_root_scroll_child_is_width_bound_not_height_clamped() -> None:
    """Law: scroll_root_sizes_to_content_not_artboard."""
    scroll_group = CleanDesignTreeNode(
        id="1:scroll",
        name="Scroll_group",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=1448.0),
        children=[
            CleanDesignTreeNode(
                id="1:text",
                name="Block",
                type=NodeType.TEXT,
                text="Content",
            )
        ],
    )
    footer = CleanDesignTreeNode(
        id="1:footer",
        name="Footer",
        type=NodeType.ROW,
        sizing=Sizing(width=390.0, height=106.0),
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(
            horizontal="LEFT_RIGHT",
            vertical="BOTTOM",
            top=738.0,
            width=390.0,
            height=106.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:tab",
                name="Tab",
                type=NodeType.BUTTON,
                sizing=Sizing(width=40.0, height=40.0),
            )
        ],
    )
    root = CleanDesignTreeNode(
        id="1:root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:status",
                name="Status",
                type=NodeType.ROW,
                sizing=Sizing(width=390.0, height=44.0),
            ),
            scroll_group,
            footer,
        ],
    )
    layout = render_layout_file(
        root,
        feature_name="tall_screen_scroll",
        uses_svg=False,
        responsive_enabled=False,
    )["lib/generated/tall_screen_scroll_layout.dart"]
    compact = layout.replace(" ", "").replace("\n", "")
    assert "SingleChildScrollView(" in layout
    assert "SizedBox(width:390.0,child:" in compact
    assert "height:844.0,child:Column(" not in compact
    assert "maxHeight:844.0" not in compact


def test_position_only_stack_scroll_child_pins_artboard_height() -> None:
    """Law: stack_scroll_viewport_child_requires_bounded_height."""
    status = CleanDesignTreeNode(
        id="1:status",
        name="Status",
        type=NodeType.ROW,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(top=0.0, width=375.0, height=44.0),
        children=[
            CleanDesignTreeNode(
                id="1:clock",
                name="Clock",
                type=NodeType.TEXT,
                text="9:41",
            )
        ],
    )
    content = CleanDesignTreeNode(
        id="1:content",
        name="Form",
        type=NodeType.COLUMN,
        sizing=Sizing(width=343.0, height=561.0),
        stack_placement=StackPlacement(left=16.0, top=125.5, width=343.0, height=561.0),
        children=[
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Login",
            )
        ],
    )
    home = CleanDesignTreeNode(
        id="1:home",
        name="Home",
        type=NodeType.ROW,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(
            vertical="BOTTOM",
            bottom=3.0,
            width=375.0,
            height=34.0,
        ),
        children=[],
    )
    root = CleanDesignTreeNode(
        id="1:root",
        name="Login",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=375.0, height=812.0),
        children=[status, content, home],
    )
    layout = render_layout_file(
        root,
        feature_name="position_only_stack_scroll",
        uses_svg=False,
        responsive_enabled=False,
    )["lib/generated/position_only_stack_scroll_layout.dart"]
    compact = layout.replace(" ", "").replace("\n", "")
    assert "SingleChildScrollView(" in layout
    assert "SizedBox(width:375.0,height:812.0,child:" in compact
    assert "SizedBox(width:375.0,child:Stack(" not in compact


def test_static_tall_column_scroll_shell_tolerates_fractional_metric_drift() -> None:
    """Static fallback scroll must not pin Column(max) inside a fixed artboard height."""
    root = CleanDesignTreeNode(
        id="1:root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=390.0, height=1332.9),
        children=[
            CleanDesignTreeNode(
                id="1:body",
                name="Body",
                type=NodeType.COLUMN,
                sizing=Sizing(width=390.0, height=1300.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:text",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Order",
                    )
                ],
            )
        ],
    )
    layout = render_layout_file(
        root,
        feature_name="tall_static_column",
        uses_svg=False,
        responsive_enabled=False,
    )["lib/generated/tall_static_column_layout.dart"]
    compact = layout.replace(" ", "").replace("\n", "")
    assert "SingleChildScrollView(" in layout
    assert "OverflowBox(" in layout
    assert "maxHeight:1332.9" in compact
    assert "height:1332.9,child:Column(" not in compact
    assert "mainAxisSize:MainAxisSize.min" in compact
