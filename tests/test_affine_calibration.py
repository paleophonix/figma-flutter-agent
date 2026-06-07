"""Geometry calibration: affine parse and Matrix4 emit (RC-1..RC-3)."""

from __future__ import annotations

import math

import pytest

from figma_flutter_agent.generator.geometry.affine import (
    affine_det,
    compose_affine,
    expand_aabb,
    linear_affine,
    matrix4_compose_expr,
    matrix4_linear_expr,
    transform_point,
)
from figma_flutter_agent.generator.geometry.emit_invariants import (
    validate_emit_geometry_invariants,
)
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.parser.geometry_frames import affine2_from_figma_node
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_affine_preserves_determinant() -> None:
    raw = {
        "relativeTransform": [
            [-1.0, 0.0, 10.0],
            [0.0, 1.0, 5.0],
        ],
    }
    affine = affine2_from_figma_node(raw)
    assert math.isclose(affine.a, -1.0, abs_tol=1e-6)
    assert affine_det(affine) < 0
    expr = matrix4_linear_expr(linear_affine(affine))
    assert expr is not None
    assert "rotateZ" not in expr
    unit_corners = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
    expected = [transform_point(affine, x, y) for x, y in unit_corners]
    for (x, y), (ex, ey) in zip(unit_corners, expected, strict=True):
        mapped = transform_point(affine, x, y)
        assert mapped[0] == pytest.approx(ex, abs=1e-6)
        assert mapped[1] == pytest.approx(ey, abs=1e-6)


def test_transform_no_double_translate() -> None:
    local = Affine2(a=0.0, b=1.0, c=-1.0, d=0.0, tx=12.0, ty=8.0)
    linear = linear_affine(local)
    expr = matrix4_compose_expr(linear)
    assert expr is not None
    assert "..translate" not in expr
    assert "Alignment.topLeft" in expr


def test_negative_inset_vector_stays_in_viewport() -> None:
    child = CleanDesignTreeNode(
        id="vec",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=40.0, height=40.0),
        geometry_frame=GeometryFrame(
            local_transform=Affine2(tx=-5.0, ty=10.0),
            intrinsic_size=GeomRect(width=40.0, height=40.0),
            layout_rect=GeomRect(x=-5.0, y=10.0, width=40.0, height=40.0),
            placement_origin=GeomRect(x=-5.0, y=10.0),
            parsed_world_aabb=GeomRect(x=0.0, y=10.0, width=35.0, height=40.0),
            world_aabb=GeomRect(x=0.0, y=10.0, width=35.0, height=40.0),
        ),
        stack_placement=StackPlacement(left=-5.0, top=10.0, width=40.0, height=40.0),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=360.0, height=640.0),
        geometry_frame=GeometryFrame(
            intrinsic_size=GeomRect(width=360.0, height=640.0),
            layout_rect=GeomRect(width=360.0, height=640.0),
        ),
        children=[child],
    )
    planned = plan_geometry_tree(root)
    slot = planned.children[0].layout_slot
    assert slot is not None
    assert slot.positioned_pins is not None
    assert slot.positioned_pins.left == -5.0
    assert slot.slot_rect.width == 40.0


def test_world_cascade_reproject() -> None:
    local = Affine2(a=math.cos(0.5), b=math.sin(0.5), c=-math.sin(0.5), d=math.cos(0.5))
    world = compose_affine(Affine2(), local)
    derived = expand_aabb(world, 50.0, 20.0)
    assert derived.width > 20.0


def test_emit_reproject_skips_axis_aligned_stack_pins() -> None:
    from figma_flutter_agent.generator.geometry.emit_invariants import (
        _emit_reproject_residual,
    )
    from figma_flutter_agent.schemas import AxisPins

    pins = AxisPins(
        free_horizontal="left",
        free_vertical="bottom",
        left=0.0,
        top=706.0,
        bottom=0.0,
        width=390.0,
        height=138.0,
    )
    residual = Affine2(tx=0.0, ty=737.9736328125)
    err = _emit_reproject_residual(
        origin_x=0.0,
        origin_y=738.0,
        pins=pins,
        residual=residual,
        intrinsic_width=390.0,
        intrinsic_height=106.0,
    )
    assert err == 0.0


def test_emit_reproject_checks_rotated_residual() -> None:
    from figma_flutter_agent.generator.geometry.emit_invariants import (
        _emit_reproject_residual,
    )
    from figma_flutter_agent.schemas import AxisPins

    pins = AxisPins(
        free_horizontal="left",
        free_vertical="top",
        left=10.0,
        top=20.0,
        width=40.0,
        height=30.0,
    )
    residual = Affine2(a=0.0, b=1.0, c=-1.0, d=0.0, tx=10.0, ty=50.0)
    err = _emit_reproject_residual(
        origin_x=10.0,
        origin_y=20.0,
        pins=pins,
        residual=residual,
        intrinsic_width=40.0,
        intrinsic_height=30.0,
    )
    assert err <= 0.25
    shifted = _emit_reproject_residual(
        origin_x=12.0,
        origin_y=20.0,
        pins=pins,
        residual=residual,
        intrinsic_width=40.0,
        intrinsic_height=30.0,
    )
    assert shifted > 0.25


def test_t1_invariant_catches_emit_translate() -> None:
    tree = CleanDesignTreeNode(
        id="n1",
        name="Box",
        type=NodeType.CONTAINER,
        layout_slot=__import__(
            "figma_flutter_agent.schemas", fromlist=["LayoutSlotIr"]
        ).LayoutSlotIr(
            residual_matrix=Affine2(a=0.0, b=1.0, c=-1.0, d=0.0),
        ),
    )
    bad_source = (
        "Positioned(left: 0.0, top: 0.0, key: ValueKey('figma-n1'), "
        "child: Transform(alignment: Alignment.center, "
        "transform: Matrix4.identity()..translate(5, 5)..rotateZ(1.0), child: Container()))"
    )
    violations = validate_emit_geometry_invariants(tree, bad_source)
    codes = {item.code for item in violations}
    assert "inv_emit_no_translate" in codes
