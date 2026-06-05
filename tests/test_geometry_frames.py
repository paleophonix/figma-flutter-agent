"""Geometry frame hydration from Figma REST nodes."""

from __future__ import annotations

import math

import pytest

from figma_flutter_agent.errors import ParseError
from figma_flutter_agent.generator.geometry.affine import aabb_residual, expand_aabb, geom_epsilon
from figma_flutter_agent.parser.geometry_frames import (
    affine2_from_figma_node,
    attach_geometry_frames,
    hydrate_geometry_frame,
)
from figma_flutter_agent.schemas import Affine2, CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def test_affine2_from_figma_node_preserves_reflection_det() -> None:
    raw = {
        "relativeTransform": [
            [-1.0, 0.0, 12.5],
            [0.0, 1.0, 40.0],
        ],
        "absoluteBoundingBox": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0},
    }
    affine = affine2_from_figma_node(raw)
    assert math.isclose(affine.a, -1.0, abs_tol=1e-6)
    assert math.isclose(affine.tx, 12.5, abs_tol=1e-6)
    assert math.isclose(affine.ty, 40.0, abs_tol=1e-6)


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
    assert frame.intrinsic_size.width == 33.333
    assert frame.parsed_world_aabb is not None
    assert frame.parsed_world_aabb.x == 10.0


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


def test_intrinsic_is_local_size_for_rotated() -> None:
    cos45 = math.sqrt(2) / 2
    sin45 = cos45
    local = Affine2(a=cos45, b=-sin45, c=sin45, d=cos45, tx=10.0, ty=20.0)
    raw = {
        "relativeTransform": [
            [cos45, sin45, 10.0],
            [-sin45, cos45, 20.0],
        ],
        "size": {"x": 100.0, "y": 40.0},
    }
    expected_aabb = expand_aabb(local, 100.0, 40.0)
    raw["absoluteBoundingBox"] = {
        "x": expected_aabb.x,
        "y": expected_aabb.y,
        "width": expected_aabb.width,
        "height": expected_aabb.height,
    }
    frame = hydrate_geometry_frame(raw, NodeStyle())
    assert math.isclose(frame.intrinsic_size.width, 100.0, abs_tol=1e-6)
    assert math.isclose(frame.intrinsic_size.height, 40.0, abs_tol=1e-6)
    assert math.isclose(frame.layout_rect.width, 100.0, abs_tol=1e-6)
    assert math.isclose(frame.layout_rect.height, 40.0, abs_tol=1e-6)
    derived = expand_aabb(local, frame.intrinsic_size.width, frame.intrinsic_size.height)
    reference = frame.parsed_world_aabb
    assert reference is not None
    assert aabb_residual(reference, derived) <= geom_epsilon()


def test_affine2_from_figma_node_absent_matrix_is_identity() -> None:
    raw = {"absoluteBoundingBox": {"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}}
    affine = affine2_from_figma_node(raw)
    assert affine.a == 1.0 and affine.d == 1.0


def test_affine2_from_figma_node_malformed_matrix_raises() -> None:
    raw = {
        "id": "node-42",
        "relativeTransform": "not-a-matrix",
    }
    with pytest.raises(ParseError, match="malformed relativeTransform at node node-42"):
        affine2_from_figma_node(raw, node_id="node-42")


def test_intrinsic_unchanged_for_axis_aligned() -> None:
    raw = {
        "relativeTransform": [[1.0, 0.0, 3.333], [0.0, 1.0, 7.777]],
        "absoluteBoundingBox": {"x": 10.0, "y": 20.0, "width": 33.333, "height": 44.444},
    }
    frame = hydrate_geometry_frame(raw, NodeStyle())
    assert frame.layout_rect.x == 3.333
    assert frame.layout_rect.y == 7.777
    assert frame.intrinsic_size.width == 33.333
    assert frame.intrinsic_size.height == 44.444
    assert frame.parsed_world_aabb is not None
    assert frame.parsed_world_aabb.x == 10.0


def test_intrinsic_fallback_when_size_absent() -> None:
    local = Affine2(a=0.866, b=-0.5, c=0.5, d=0.866, tx=40.0, ty=80.0)
    expected_aabb = expand_aabb(local, 160.0, 100.0)
    raw = {
        "relativeTransform": [[0.866, 0.5, 40.0], [-0.5, 0.866, 80.0]],
        "absoluteBoundingBox": {
            "x": expected_aabb.x,
            "y": expected_aabb.y,
            "width": expected_aabb.width,
            "height": expected_aabb.height,
        },
    }
    frame = hydrate_geometry_frame(raw, NodeStyle())
    assert frame.intrinsic_size.width > 0.0
    assert frame.intrinsic_size.height > 0.0
    derived = expand_aabb(local, frame.intrinsic_size.width, frame.intrinsic_size.height)
    reference = frame.parsed_world_aabb
    assert reference is not None
    assert aabb_residual(reference, derived) <= geom_epsilon()
