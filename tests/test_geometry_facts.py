"""Unit tests for universal geometry band facts (T3)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.geometry_facts import (
    CARD_METADATA_MAX_WIDTH,
    COMPACT_CHIP_HOST_MAX_WIDTH,
    MIN_CHIP_HORIZONTAL_PADDING,
    NUMERIC_GLYPH_OVERLAY_MAX_WIDTH,
    PRODUCT_TILE_WIDTH_MAX,
    PRODUCT_TILE_WIDTH_MIN,
    SQUARE_ICON_CONTROL_MAX,
    SQUARE_ICON_CONTROL_MIN,
    SQUARE_TILE_MIN_EDGE,
    STATUS_PILL_MAX_HEIGHT,
    TIGHT_PILL_MAX_HEIGHT,
    TIGHT_STACK_TEXT_MAX_HEIGHT,
    VIEWPORT_CHROME_MAX_HEIGHT,
    VIEWPORT_CHROME_MIN_WIDTH,
    bounded_width_at_most,
    height_within_band,
    near_square_aspect,
    node_horizontal_padding_at_least,
    square_bounds_within_band,
    square_tile_min_extent,
    viewport_chrome_band_size,
    width_within_band,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Padding, Sizing


def test_height_within_band_uses_named_thresholds() -> None:
    assert height_within_band(30.0, max_height=TIGHT_PILL_MAX_HEIGHT)
    assert not height_within_band(36.0, max_height=TIGHT_PILL_MAX_HEIGHT)
    assert height_within_band(36.0, max_height=STATUS_PILL_MAX_HEIGHT)
    assert not height_within_band(40.0, max_height=STATUS_PILL_MAX_HEIGHT)


def test_square_bounds_within_band_matches_icon_control_window() -> None:
    assert square_bounds_within_band(
        44.0,
        44.0,
        min_edge=SQUARE_ICON_CONTROL_MIN,
        max_edge=SQUARE_ICON_CONTROL_MAX,
    )
    assert not square_bounds_within_band(
        36.0,
        44.0,
        min_edge=SQUARE_ICON_CONTROL_MIN,
        max_edge=SQUARE_ICON_CONTROL_MAX,
    )


def test_chip_host_geometry_facts() -> None:
    node = CleanDesignTreeNode(
        id="1:1",
        name="Chip",
        type=NodeType.ROW,
        sizing=Sizing(width=120.0, height=28.0),
        padding=Padding(left=8.0, right=8.0),
        children=[],
    )
    assert bounded_width_at_most(node.sizing, COMPACT_CHIP_HOST_MAX_WIDTH)
    assert node_horizontal_padding_at_least(node, MIN_CHIP_HORIZONTAL_PADDING)


def test_column_stack_geometry_bands() -> None:
    assert height_within_band(28.0, max_height=TIGHT_STACK_TEXT_MAX_HEIGHT)
    assert square_tile_min_extent(64.0, 64.0, min_edge=SQUARE_TILE_MIN_EDGE)
    assert not square_tile_min_extent(48.0, 64.0, min_edge=SQUARE_TILE_MIN_EDGE)
    assert near_square_aspect(64.0, 68.0)
    assert width_within_band(
        150.0,
        min_width=PRODUCT_TILE_WIDTH_MIN,
        max_width=PRODUCT_TILE_WIDTH_MAX,
    )
    assert bounded_width_at_most(Sizing(width=100.0), CARD_METADATA_MAX_WIDTH)
    assert width_within_band(
        20.0,
        min_width=0.0,
        max_width=NUMERIC_GLYPH_OVERLAY_MAX_WIDTH,
    )


def test_viewport_chrome_band_size() -> None:
    assert viewport_chrome_band_size(VIEWPORT_CHROME_MIN_WIDTH, VIEWPORT_CHROME_MAX_HEIGHT)
    assert not viewport_chrome_band_size(300.0, VIEWPORT_CHROME_MAX_HEIGHT)
