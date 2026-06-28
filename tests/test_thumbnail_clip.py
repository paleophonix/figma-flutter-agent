"""Tests for compact raster thumbnail clip shape emit."""

from figma_flutter_agent.generator.layout.widgets.thumbnail import (
    try_render_compact_raster_photo_stack,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def test_compact_square_photo_uses_figma_border_radius_not_oval() -> None:
    photo = CleanDesignTreeNode(
        id="photo",
        name="image",
        type=NodeType.IMAGE,
        image_asset_key="assets/images/sample.png",
        sizing=Sizing(width=72.0, height=72.0),
    )
    host = CleanDesignTreeNode(
        id="host",
        name="image_group",
        type=NodeType.STACK,
        style=NodeStyle(border_radius=8.0),
        sizing=Sizing(width=72.0, height=72.0),
        children=[photo],
    )

    emitted = try_render_compact_raster_photo_stack(host)

    assert emitted is not None
    assert "ClipRRect(borderRadius: BorderRadius.circular(8.0)" in emitted
    assert "ClipOval(" not in emitted


def test_compact_square_photo_without_radius_stays_oval() -> None:
    photo = CleanDesignTreeNode(
        id="photo",
        name="avatar",
        type=NodeType.IMAGE,
        image_asset_key="assets/images/sample.png",
        sizing=Sizing(width=48.0, height=48.0),
    )
    host = CleanDesignTreeNode(
        id="host",
        name="avatar",
        type=NodeType.STACK,
        sizing=Sizing(width=48.0, height=48.0),
        children=[photo],
    )

    emitted = try_render_compact_raster_photo_stack(host)

    assert emitted is not None
    assert "ClipOval(" in emitted
