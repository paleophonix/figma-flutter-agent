"""Numeric precision for clean-tree geometry and micro-style fields.

Geometry (1 decimal): layout box metrics and spacing — imperceptible sub-pixel
drift, fewer tokens in LLM payloads and generated Dart.

Micro-styles (2 decimals): letter spacing, line height ratio, opacity, rotation —
coarser rounding causes visible text drift or clipping.
"""

from __future__ import annotations

from figma_flutter_agent.schemas import Padding, Sizing, StackPlacement

GEOMETRY_DECIMALS = 1
MICRO_STYLE_DECIMALS = 2


def round_geometry(value: float | None) -> float | None:
    """Round layout geometry to one decimal place."""
    if value is None:
        return None
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
