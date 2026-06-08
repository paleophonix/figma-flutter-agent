"""Welcome/sleep screens with oversized rotated wallpaper boundaries."""

from __future__ import annotations

from figma_flutter_agent.generator.ambient_background import (
    is_screen_wallpaper_node,
    split_screen_wallpaper_children,
)
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.layout import reconcile_centered_text_placements_in_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def _welcome_sleep_root() -> CleanDesignTreeNode:
    wallpaper = CleanDesignTreeNode(
        id="3:2913",
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=605.9, height=1210.1),
        render_boundary=True,
        rotation=1.57,
        vector_asset_key="assets/illustrations/group_3_2913.svg",
        stack_placement=StackPlacement(left=-54.3, width=605.9, height=1210.1),
    )
    title = CleanDesignTreeNode(
        id="3:2956",
        name="Wecome to Sleep",
        type=NodeType.TEXT,
        text="Wecome to Sleep",
        style=NodeStyle(font_size=30.0, font_weight="w700", text_align="CENTER"),
        sizing=Sizing(width=256.0, height=41.0),
        stack_placement=StackPlacement(left=0.0, top=111.0, width=256.0, height=41.0),
    )
    button = CleanDesignTreeNode(
        id="3:2959",
        name="GET STARTED",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(left=20.0, top=695.0, width=374.0, height=63.0),
        children=[
            CleanDesignTreeNode(
                id="3:2960",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=374.0, height=63.0),
                style=NodeStyle(background_color="0xFF8E97FD", border_radius=38.0),
            ),
            CleanDesignTreeNode(
                id="3:2961",
                name="Label",
                type=NodeType.TEXT,
                text="GET STARTED",
                stack_placement=StackPlacement(left=140.0, top=24.0, width=94.0, height=14.0),
            ),
        ],
    )
    return CleanDesignTreeNode(
        id="3:2912",
        name="welcome sleep",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        style=NodeStyle(background_color="0xFF03174C"),
        children=[wallpaper, title, button],
    )


def test_screen_wallpaper_node_detects_oversized_boundary() -> None:
    root = _welcome_sleep_root()
    wallpaper = root.children[0]
    assert is_screen_wallpaper_node(wallpaper, root)
    wallpaper_nodes, foreground = split_screen_wallpaper_children(root)
    assert len(wallpaper_nodes) == 1
    assert len(foreground) == 2


def test_layout_renders_wallpaper_behind_foreground() -> None:
    root = reconcile_centered_text_placements_in_tree(_welcome_sleep_root())
    layout = render_layout_file(root, feature_name="welcome_sleep", uses_svg=True)[
        "lib/generated/welcome_sleep_layout.dart"
    ]
    assert "group_3_2913.svg" in layout
    assert layout.index("Positioned.fill") < layout.index("Wecome to Sleep")
    assert "Transform.rotate" in layout
    assert "BoxFit.cover" in layout
    assert layout.count("group_3_2913.svg") == 1
    assert "left: 79.0" in layout or "left: 79," in layout
