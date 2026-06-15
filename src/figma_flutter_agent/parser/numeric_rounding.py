"""Numeric precision for clean-tree geometry and micro-style fields.

Geometry (1 decimal): layout box metrics and spacing — imperceptible sub-pixel
drift, fewer tokens in LLM payloads and generated Dart.

Micro-styles (2 decimals): letter spacing, line height ratio, opacity, rotation —
coarser rounding causes visible text drift or clipping.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

from figma_flutter_agent.schemas import Padding, Sizing, StackPlacement

GeometryPrecision = Literal["standard", "full"]

GEOMETRY_DECIMALS = 1
FULL_GEOMETRY_DECIMALS = 4
MICRO_STYLE_DECIMALS = 2

_precision_ctx: ContextVar[GeometryPrecision] = ContextVar(
    "geometry_precision",
    default="standard",
)


@contextmanager
def geometry_precision_scope(precision: GeometryPrecision) -> Iterator[None]:
    """Temporarily set layout geometry rounding precision for the current context."""
    token = _precision_ctx.set(precision)
    try:
        yield
    finally:
        _precision_ctx.reset(token)


def round_geometry(value: float | None, *, decimals: int | None = None) -> float | None:
    """Round layout geometry to one decimal place."""
    if value is None:
        return None
    if decimals is not None:
        return round(float(value), decimals)
    if _precision_ctx.get() == "full":
        return round(float(value), FULL_GEOMETRY_DECIMALS)
    return round(float(value), GEOMETRY_DECIMALS)


def round_micro_style(value: float | None) -> float | None:
    """Round typography and visual micro-styles to two decimal places."""
    if value is None:
        return None
    return round(float(value), MICRO_STYLE_DECIMALS)


def round_padding(padding: Padding) -> Padding:
    """Return padding with geometry fields rounded to one decimal."""
    return Padding(
        top=round_geometry(padding.top) or 0.0,
        bottom=round_geometry(padding.bottom) or 0.0,
        left=round_geometry(padding.left) or 0.0,
        right=round_geometry(padding.right) or 0.0,
    )


def round_sizing(sizing: Sizing) -> Sizing:
    """Return sizing with ``width``/``height`` rounded to one decimal."""
    return sizing.model_copy(
        update={
            "width": round_geometry(sizing.width),
            "height": round_geometry(sizing.height),
        }
    )


def round_axis_prefix(positions: list[float], *, gap: float = 0.0) -> list[float]:
    """Telescopic prefix rounding for axis extent conservation (T2).

    Args:
        positions: Monotonic boundary positions including start and end.
        gap: Uniform gap between interior segments (unused when len <= 2).

    Returns:
        Rounded cumulative boundaries; segment sum equals rounded parent span.
    """
    if not positions:
        return []
    raw: list[float] = [float(positions[0])]
    for index in range(1, len(positions)):
        segment = float(positions[index]) - float(positions[index - 1])
        if index > 1 and gap:
            segment += gap
        raw.append(raw[-1] + segment)
    rounded: list[float] = []
    cumulative = 0.0
    for value in raw:
        cumulative = round_geometry(value) or 0.0
        rounded.append(cumulative)
    return rounded


def round_stack_placement(
    placement: StackPlacement,
    *,
    parent_width: float | None = None,
    parent_height: float | None = None,
) -> StackPlacement:
    """Return stack placement edges and box size rounded to one decimal.

    When horizontal pins and ``parent_width`` are set, preserves
    ``left + width + right == parent_width`` after rounding (FID-17).
    """
    left = round_geometry(placement.left) or 0.0
    top = round_geometry(placement.top) or 0.0
    right = round_geometry(placement.right) or 0.0
    bottom = round_geometry(placement.bottom) or 0.0
    width = round_geometry(placement.width)
    height = round_geometry(placement.height)
    if (
        parent_width is not None
        and placement.left is not None
        and placement.right is not None
        and width is not None
    ):
        width = round_geometry(parent_width - left - right)
    if (
        parent_height is not None
        and placement.top is not None
        and placement.bottom is not None
        and height is not None
    ):
        height = round_geometry(parent_height - top - bottom)
    return placement.model_copy(
        update={
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": width,
            "height": height,
        }
    )


def format_geometry_literal(value: float) -> str:
    """Format a geometry value for Dart source (one decimal, ``N.0`` when integral)."""
    rounded = round_geometry(value)
    assert rounded is not None
    if rounded == int(rounded):
        return f"{int(rounded)}.0"
    return f"{rounded:g}"


def format_micro_style_literal(value: float) -> str:
    """Format a micro-style value for Dart source (two decimals)."""
    rounded = round_micro_style(value)
    assert rounded is not None
    return f"{rounded:g}"
