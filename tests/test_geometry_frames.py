"""Geometry frame hydration from Figma REST nodes."""

from __future__ import annotations

import math

from figma_flutter_agent.parser.geometry_frames import (
    affine2_from_figma_node,
    attach_geometry_frames,
    hydrate_geometry_frame,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def test_affine2_from_figma_node_preserves_full_matrix() -> None:
    raw = {
        "relativeTransform": [
            [0.0, 1.0, 12.5],
            [-1.0, 0.0, 40.0],
        ],
        "absoluteBoundingBox": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0},
    }
    affine = affine2_from_figma_node(raw)
    assert math.isclose(affine.a, 0.0, abs_tol=1e-6)
    assert math.isclose(affine.c, 1.0, abs_tol=1e-6)
    assert math.isclose(affine.tx, 12.5, abs_tol=1e-6)
    assert math.isclose(affine.ty, 40.0, abs_tol=1e-6)


def test_hydrate_geometry_frame_without_early_rounding() -> None:
    raw = {
        "relativeTransform": [[1.0, 0.0, 3.333], [0.0, 1.0, 7.777]],
        "absoluteBoundingBox": {"x": 10.0, "y": 20.0, "width": 33.333, "height": 44.444},
    }
    frame = hydrate_geometry_frame(raw, NodeStyle())
    assert frame.layout_rect.x == 3.333
    assert frame.layout_rect.y == 7.777
    assert frame.layout_rect.width == 33.333
    assert frame.world_aabb.x == 10.0


def test_attach_geometry_frames_on_clean_tree_node() -> None:
    node = CleanDesignTreeNode(
        id="n1",
        name="Box",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=80.0, height=40.0),
    )
    raw = {
        "relativeTransform": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        "absoluteBoundingBox": {"x": 0.0, "y": 0.0, "width": 80.0, "height": 40.0},
    }
    enriched = attach_geometry_frames(node, raw)
    assert enriched.geometry_frame is not None
    assert enriched.geometry_frame.local_transform.a == 1.0
