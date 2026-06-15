"""IR validation and positioned dims for zero-bbox stroked vectors (LAW-GEO-STROKE-EXTENT)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.validate.graph import (
    _validate_stack_placement_bounds,
    stack_placement_bounded_for_ir,
)
from figma_flutter_agent.generator.layout.widgets import figma_positioned_dimensions
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    StackPlacement,
)

_STROKE_EXPAND = Padding(top=1.0, bottom=1.0, left=1.0, right=1.0)


def _stroked_line_node(
    *,
    width: float,
    height: float,
    placement: StackPlacement,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="stroke-line",
        name="Line",
        type=NodeType.VECTOR,
        sizing=Sizing(width=width, height=height),
        stack_placement=placement,
        style=NodeStyle(
            has_stroke=True,
            border_width=2.0,
            render_bounds_expand=_STROKE_EXPAND,
        ),
    )


def test_zero_width_stroked_vector_recovers_horizontal_extent() -> None:
    node = _stroked_line_node(
        width=0.0,
        height=8.0,
        placement=StackPlacement(
            left=4.0,
            right=4.0,
            width=0.0,
            height=8.0,
        ),
    )
    width, height = figma_positioned_dimensions(node)
    assert width == 2.0
    assert height == 8.0
    assert stack_placement_bounded_for_ir(node)
    _validate_stack_placement_bounds(node)


def test_zero_height_stroked_vector_recovers_vertical_extent() -> None:
    node = _stroked_line_node(
        width=8.0,
        height=0.0,
        placement=StackPlacement(
            top=4.0,
            bottom=4.0,
            width=8.0,
            height=0.0,
        ),
    )
    width, height = figma_positioned_dimensions(node)
    assert width == 8.0
    assert height == 2.0
    assert stack_placement_bounded_for_ir(node)
    _validate_stack_placement_bounds(node)


def test_zero_bbox_without_stroke_still_fails_horizontal_bounds() -> None:
    node = CleanDesignTreeNode(
        id="flat",
        name="Flat",
        type=NodeType.VECTOR,
        sizing=Sizing(width=0.0, height=8.0),
        stack_placement=StackPlacement(
            top=0.0,
            width=0.0,
            height=8.0,
        ),
        style=NodeStyle(),
    )
    assert not stack_placement_bounded_for_ir(node)
    with pytest.raises(GenerationError, match="bounded width"):
        _validate_stack_placement_bounds(node)


def test_positive_bbox_ignores_render_bounds_expand() -> None:
    node = CleanDesignTreeNode(
        id="tile",
        name="Tile",
        type=NodeType.VECTOR,
        sizing=Sizing(width=100.0, height=100.0),
        stack_placement=StackPlacement(
            left=0.0,
            top=0.0,
            width=100.0,
            height=100.0,
        ),
        style=NodeStyle(
            has_stroke=True,
            render_bounds_expand=Padding(top=25.0, bottom=35.0, left=30.0, right=30.0),
        ),
    )
    width, height = figma_positioned_dimensions(node)
    assert width == 100.0
    assert height == 100.0
