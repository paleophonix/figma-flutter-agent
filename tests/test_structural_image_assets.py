"""Tests for structural raster asset propagation."""

from __future__ import annotations

from figma_flutter_agent.parser.boundaries.assets import (
    resolve_structural_duplicate_image_assets,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def _photo_stack(node_id: str, photo_id: str, *, image_key: str | None) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Photo stack",
        type=NodeType.STACK,
        sizing=Sizing(width=170.5, height=171.0),
        children=[
            CleanDesignTreeNode(
                id=photo_id,
                name="Photo",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=171.0, height=171.0),
                image_asset_key=image_key,
            )
        ],
    )


def test_structural_duplicate_image_assets_copy_representative_key() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        children=[
            _photo_stack("610:539", "610:540", image_key="assets/images/image_610_540.png"),
            _photo_stack("610:653", "610:654", image_key=None),
        ],
    )
    resolve_structural_duplicate_image_assets(tree)
    duplicate = tree.children[1].children[0]
    assert duplicate.image_asset_key == "assets/images/image_610_540.png"
