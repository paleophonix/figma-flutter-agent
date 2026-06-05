"""Affine matrix utilities for translation-theory planning (T1)."""

from __future__ import annotations

import math

from figma_flutter_agent.schemas import Affine2, GeomRect

_GEOM_EPSILON = 0.25


def compose_affine(parent: Affine2, local: Affine2) -> Affine2:
    """Return ``parent · local`` (Figma parent-relative cascade)."""
    return Affine2(
        a=parent.a * local.a + parent.c * local.b,
        b=parent.b * local.a + parent.d * local.b,
        c=parent.a * local.c + parent.c * local.d,
        d=parent.b * local.c + parent.d * local.d,
        tx=parent.a * local.tx + parent.c * local.ty + parent.tx,
        ty=parent.b * local.tx + parent.d * local.ty + parent.ty,
    )


def expand_aabb(transform: Affine2, width: float, height: float) -> GeomRect:
    """Axis-aligned bounds of rectangle ``(0,0,w,h)`` under ``transform``."""
    corners = (
        _transform_point(transform, 0.0, 0.0),
        _transform_point(transform, width, 0.0),
        _transform_point(transform, 0.0, height),
        _transform_point(transform, width, height),
    )
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    return GeomRect(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)


def _transform_point(transform: Affine2, x: float, y: float) -> tuple[float, float]:
    return (
        transform.a * x + transform.c * y + transform.tx,
        transform.b * x + transform.d * y + transform.ty,
    )


def aabb_residual(expected: GeomRect, actual: GeomRect) -> float:
    """Return max corner error between two axis-aligned boxes."""
    return max(
        abs(expected.x - actual.x),
        abs(expected.y - actual.y),
        abs(expected.width - actual.width),
        abs(expected.height - actual.height),
    )


def matrix4_compose_expr(transform: Affine2) -> str | None:
    """Emit Dart ``Transform`` prefix with ``Matrix4`` composition (T1)."""
    angle = math.atan2(transform.b, transform.a)
    sx = math.hypot(transform.a, transform.b)
    sy = math.hypot(transform.c, transform.d)
    if (
        abs(angle) < 1e-6
        and abs(sx - 1.0) < 1e-6
        and abs(sy - 1.0) < 1e-6
        and abs(transform.tx) < 1e-6
        and abs(transform.ty) < 1e-6
    ):
        return None
    angle_lit = f"{angle:.6g}"
    sx_lit = f"{sx:.6g}"
    sy_lit = f"{sy:.6g}"
    tx_lit = f"{transform.tx:.6g}"
    ty_lit = f"{transform.ty:.6g}"
    return (
        "Transform("
        "alignment: Alignment.topLeft, "
        f"transform: Matrix4.identity()"
        f"..translate({tx_lit}, {ty_lit})"
        f"..rotateZ({angle_lit})"
        f"..scale({sx_lit}, {sy_lit}, 1.0), "
        "child: "
    )


def matrix4_close_suffix() -> str:
    return ")"


def geom_epsilon() -> float:
    return _GEOM_EPSILON
