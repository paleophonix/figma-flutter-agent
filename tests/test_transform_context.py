"""TransformContext parsing from Figma relativeTransform (WP-D)."""

from __future__ import annotations

import math

from figma_flutter_agent.parser.geometry import (
    rotation_degrees_from_figma_node,
    transform_context_from_figma_node,
)


def test_transform_context_from_relative_transform_matrix() -> None:
    raw = {
        "relativeTransform": [
            [0.0, 1.0, 10.0],
            [-1.0, 0.0, 20.0],
        ],
    }
    ctx = transform_context_from_figma_node(raw)
    assert ctx is not None
    assert ctx.translate_x == 10.0
    assert ctx.translate_y == 20.0
    assert ctx.rotation_rad is not None
    assert abs(ctx.rotation_rad + math.pi / 2) < 0.01


def test_rotation_degrees_prefers_explicit_field() -> None:
    raw = {"rotation": 45.0, "relativeTransform": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]}
    assert rotation_degrees_from_figma_node(raw) == 45.0
