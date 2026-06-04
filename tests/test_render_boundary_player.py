"""Render-boundary collapse must not flatten player chrome."""

from __future__ import annotations

from figma_flutter_agent.parser.render_boundary import collapse_render_boundaries
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement


def _play_pause_stack() -> CleanDesignTreeNode:
    bars = CleanDesignTreeNode(
        id="bar",
        name="Bar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=6.0, height=24.0),
        style={"backgroundColor": "0xFFFFFFFF"},
    )
    core = CleanDesignTreeNode(
        id="core",
        name="Core",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=88.0, height=88.0),
        style={"backgroundColor": "0xFF3F414E", "borderRadius": 44.0},
    )
    return CleanDesignTreeNode(
        id="play",
        name="Play",
        type=NodeType.STACK,
        sizing=Sizing(width=109.0, height=109.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=109.0, height=109.0),
        children=[core, bars, bars],
    )


def test_render_boundary_skips_play_pause_stack() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[_play_pause_stack()],
    )
    result = collapse_render_boundaries(root)
    play = root.children[0]
    assert result.collapsed_count == 0
    assert not play.render_boundary
    assert len(play.children) >= 2
