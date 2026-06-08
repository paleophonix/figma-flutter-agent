"""Play/pause native control rendering tests."""

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_play_pause_stack_renders_native_control() -> None:
    pause = CleanDesignTreeNode(
        id="2",
        name="Pause Control",
        type=NodeType.STACK,
        sizing=Sizing(width=96.0, height=96.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=95.0, top=6.5),
        children=[
            CleanDesignTreeNode(
                id="3",
                name="Core",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=76.0, height=76.0),
                style=NodeStyle(background_color="0xFF3F414E", border_radius=38.0),
            ),
            CleanDesignTreeNode(
                id="4",
                name="Bar 1",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=6.5, height=24.0),
                style=NodeStyle(background_color="0xFFFBFBFB", border_radius=14.0),
            ),
            CleanDesignTreeNode(
                id="5",
                name="Bar 2",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=6.5, height=24.0),
                style=NodeStyle(background_color="0xFFFBFBFB", border_radius=14.0),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[pause],
    )

    layout = render_layout_file(screen, feature_name="player", uses_svg=False)[
        "lib/generated/player_layout.dart"
    ]

    assert "alignment: Alignment.center" in layout
    assert "Row(mainAxisSize: MainAxisSize.min" in layout
    assert "BoxShape.circle" in layout
    assert "width: 76.0, height: 76.0" in layout


def test_play_pause_heuristic_does_not_replace_screen_root() -> None:
    pause = CleanDesignTreeNode(
        id="2",
        name="Pause Control",
        type=NodeType.STACK,
        sizing=Sizing(width=96.0, height=96.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=95.0, top=6.5),
        children=[
            CleanDesignTreeNode(
                id="3",
                name="Core",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=76.0, height=76.0),
                style=NodeStyle(background_color="0xFF3F414E", border_radius=38.0),
            ),
            CleanDesignTreeNode(
                id="4",
                name="Bar 1",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=6.5, height=24.0),
                style=NodeStyle(background_color="0xFFFBFBFB", border_radius=14.0),
            ),
            CleanDesignTreeNode(
                id="5",
                name="Bar 2",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=6.5, height=24.0),
                style=NodeStyle(background_color="0xFFFBFBFB", border_radius=14.0),
            ),
        ],
    )
    title = CleanDesignTreeNode(
        id="6",
        name="Title",
        type=NodeType.TEXT,
        text="Music",
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20.0, top=120.0),
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[title, pause],
    )

    layout = render_layout_file(screen, feature_name="player", uses_svg=False)[
        "lib/generated/player_layout.dart"
    ]

    assert 1 <= layout.count("alignment: Alignment.center") <= 2
    assert "Text('Music'" in layout
