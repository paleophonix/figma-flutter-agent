"""Auth pill left-icon vertical centering in the layout reconcile pass."""

from __future__ import annotations

from figma_flutter_agent.parser.layout import reconcile_auth_button_icon_placements_in_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def _auth_pill_with_icon(*, icon_top: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="btn:1",
        name="pill",
        type=NodeType.BUTTON,
        sizing=Sizing(
            widthMode=SizingMode.FIXED,
            heightMode=SizingMode.FIXED,
            width=374.0,
            height=63.0,
        ),
        stack_placement=StackPlacement(
            left=20.0,
            top=100.0,
            width=374.0,
            height=63.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="icon:1",
                name="icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=24.0, height=24.0),
                stack_placement=StackPlacement(
                    left=30.0,
                    top=icon_top,
                    width=24.0,
                    height=24.0,
                ),
                vector_asset_key="assets/icons/icon.svg",
            ),
        ],
    )


def test_reconcile_auth_button_icon_placements_centers_high_icons() -> None:
    tree = reconcile_auth_button_icon_placements_in_tree(_auth_pill_with_icon(icon_top=7.9))
    icon = tree.children[0]
    assert icon.stack_placement is not None
    assert icon.stack_placement.top == 19.5


def test_reconcile_auth_button_icon_placements_handles_bottom_anchored_icons() -> None:
    pill = CleanDesignTreeNode(
        id="btn:2",
        name="pill",
        type=NodeType.BUTTON,
        sizing=Sizing(
            widthMode=SizingMode.FIXED,
            heightMode=SizingMode.FIXED,
            width=374.0,
            height=63.0,
        ),
        stack_placement=StackPlacement(
            left=20.0,
            top=100.0,
            width=374.0,
            height=63.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="icon:2",
                name="icon",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
                stack_placement=StackPlacement(
                    left=29.0,
                    bottom=19.5,
                    width=24.0,
                    height=24.0,
                ),
                vector_asset_key="assets/icons/group.svg",
            ),
        ],
    )
    tree = reconcile_auth_button_icon_placements_in_tree(pill)
    icon = tree.children[0]
    assert icon.stack_placement is not None
    assert icon.stack_placement.top == 19.5
    assert icon.stack_placement.bottom is None
