"""Legacy-path rotation emit must use radians (NEW-MTX-01)."""

from __future__ import annotations

import math

from figma_flutter_agent.generator.layout.widgets import _apply_node_transform
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_legacy_rotation_emits_radians() -> None:
    node = CleanDesignTreeNode(
        id="rot",
        name="Rotated",
        type=NodeType.CONTAINER,
        rotation=45.0,
        rotation_rad=math.radians(45.0),
        sizing=Sizing(width=100.0, height=50.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=100.0, height=50.0),
    )
    emitted = _apply_node_transform(node, "Container()")
    assert "Transform.rotate" in emitted
    assert "angle: 45.0" not in emitted
    assert "angle: 0.79" in emitted


def test_rotation_rad_preferred_over_degrees_field() -> None:
    node = CleanDesignTreeNode(
        id="rad",
        name="Rad",
        type=NodeType.VECTOR,
        rotation=90.0,
        rotation_rad=1.5707963267948966,
        sizing=Sizing(width=24.0, height=24.0),
    )
    emitted = _apply_node_transform(node, "Icon(Icons.star)")
    assert "angle: 1.57" in emitted
