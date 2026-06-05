"""T1 affine cascade and Matrix4 emit."""

from __future__ import annotations

import math

from figma_flutter_agent.generator.geometry_affine import (
    aabb_residual,
    compose_affine,
    expand_aabb,
    geom_epsilon,
    linear_affine,
    matrix4_compose_expr,
)
from figma_flutter_agent.generator.geometry_planner import plan_geometry_tree
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    GeomRect,
    GeometryFrame,
    NodeType,
    Sizing,
)


def test_compose_affine_parent_child() -> None:
    parent = Affine2(a=2.0, d=2.0, tx=10.0, ty=5.0)
    local = Affine2(tx=3.0, ty=4.0)
    world = compose_affine(parent, local)
    assert math.isclose(world.tx, 16.0, abs_tol=1e-6)
    assert math.isclose(world.ty, 13.0, abs_tol=1e-6)


def test_expand_aabb_rotated_corners() -> None:
    angle = math.pi / 4
    transform = Affine2(
        a=math.cos(angle),
        b=math.sin(angle),
        c=-math.sin(angle),
        d=math.cos(angle),
    )
    box = expand_aabb(transform, 10.0, 10.0)
    assert box.width > 10.0
    assert box.height > 10.0


def test_world_cascade_matches_reproject_invariant() -> None:
    child = CleanDesignTreeNode(
        id="child",
        name="Child",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=50.0, height=20.0),
        geometry_frame=GeometryFrame(
            local_transform=Affine2(tx=5.0, ty=10.0),
            layout_rect=GeomRect(x=5.0, y=10.0, width=50.0, height=20.0),
            intrinsic_size=GeomRect(width=50.0, height=20.0),
            parsed_world_aabb=GeomRect(x=5.0, y=10.0, width=50.0, height=20.0),
        ),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=400.0),
        geometry_frame=GeometryFrame(
            local_transform=Affine2(),
            layout_rect=GeomRect(width=200.0, height=400.0),
            intrinsic_size=GeomRect(width=200.0, height=400.0),
        ),
        children=[child],
    )
    planned = plan_geometry_tree(root)
    frame = planned.children[0].geometry_frame
    assert frame is not None
    assert frame.world_transform is not None
    derived = expand_aabb(
        frame.world_transform, frame.intrinsic_size.width, frame.intrinsic_size.height
    )
    assert aabb_residual(frame.world_aabb, derived) <= geom_epsilon()


def test_matrix4_compose_expr_for_rotation() -> None:
    angle = math.pi / 6
    transform = Affine2(
        a=math.cos(angle),
        b=math.sin(angle),
        c=-math.sin(angle),
        d=math.cos(angle),
        tx=12.0,
        ty=8.0,
    )
    expr = matrix4_compose_expr(linear_affine(transform))
    assert expr is not None
    assert "rotateZ" not in expr
    assert "Matrix4(" in expr
