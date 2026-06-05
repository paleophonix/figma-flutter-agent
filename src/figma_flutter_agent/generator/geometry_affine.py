"""Affine matrix utilities for translation-theory planning (T1)."""

from __future__ import annotations

from figma_flutter_agent.schemas import Affine2, GeomRect

_GEOM_EPSILON = 0.25
_SHEAR_EPSILON = 1e-4


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


def affine_det(affine: Affine2) -> float:
    """Return determinant of the 2×2 linear block."""
    return affine.a * affine.d - affine.b * affine.c


def linear_affine(affine: Affine2) -> Affine2:
    """Return linear part only (translation belongs to layout slot)."""
    return Affine2(a=affine.a, b=affine.b, c=affine.c, d=affine.d, tx=0.0, ty=0.0)


def is_axis_aligned(affine: Affine2, *, epsilon: float = _SHEAR_EPSILON) -> bool:
    """Return True when the linear block is approximately axis-aligned."""
    return abs(affine.b) <= epsilon and abs(affine.c) <= epsilon


def has_non_trivial_linear(affine: Affine2) -> bool:
    """Return True when the linear block differs from identity."""
    linear = linear_affine(affine)
    return not (
        abs(linear.a - 1.0) < 1e-6
        and abs(linear.d - 1.0) < 1e-6
        and abs(linear.b) < 1e-6
        and abs(linear.c) < 1e-6
    )


def requires_raster_tier(affine: Affine2) -> bool:
    """Return True when declarative Matrix4 emit is unsafe (strong shear)."""
    if abs(affine_det(affine)) < 1e-6:
        return True
    if is_axis_aligned(affine):
        return False
    det = abs(affine_det(affine))
    scale = max(abs(affine.a), abs(affine.b), abs(affine.c), abs(affine.d))
    if scale < 1e-6:
        return True
    return det / scale < 0.05


def transform_point(transform: Affine2, x: float, y: float) -> tuple[float, float]:
    """Apply ``transform`` to a point."""
    return (
        transform.a * x + transform.c * y + transform.tx,
        transform.b * x + transform.d * y + transform.ty,
    )


def expand_aabb(transform: Affine2, width: float, height: float) -> GeomRect:
    """Axis-aligned bounds of rectangle ``(0,0,w,h)`` under ``transform``."""
    corners = (
        transform_point(transform, 0.0, 0.0),
        transform_point(transform, width, 0.0),
        transform_point(transform, 0.0, height),
        transform_point(transform, width, height),
    )
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    return GeomRect(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)


def aabb_residual(expected: GeomRect, actual: GeomRect) -> float:
    """Return max corner error between two axis-aligned boxes."""
    return max(
        abs(expected.x - actual.x),
        abs(expected.y - actual.y),
        abs(expected.width - actual.width),
        abs(expected.height - actual.height),
    )


def matrix4_linear_expr(transform: Affine2) -> str | None:
    """Emit Dart ``Transform`` with raw linear ``Matrix4`` block (no translate)."""
    linear = linear_affine(transform)
    if not has_non_trivial_linear(linear):
        return None
    a, b, c, d = linear.a, linear.b, linear.c, linear.d
    return (
        "Transform("
        "alignment: Alignment.center, "
        f"transform: Matrix4({a:.6g}, {b:.6g}, 0.0, 0.0, "
        f"{c:.6g}, {d:.6g}, 0.0, 0.0, "
        "0.0, 0.0, 1.0, 0.0, "
        "0.0, 0.0, 0.0, 1.0), "
        "child: "
    )


def matrix4_compose_expr(transform: Affine2) -> str | None:
    """Emit calibrated linear ``Matrix4`` (alias for ``matrix4_linear_expr``)."""
    return matrix4_linear_expr(transform)


def matrix4_close_suffix() -> str:
    return ")"


def geom_epsilon() -> float:
    return _GEOM_EPSILON
