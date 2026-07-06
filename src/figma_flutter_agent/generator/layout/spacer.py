"""Emit helpers for fixed-size spacer leaves."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_MAX_SPACER_AXIS_PX = 48.0


def layout_fact_dimensioned_spacer_leaf(node: CleanDesignTreeNode) -> bool:
    """True for leaf layout nodes whose bounds encode explicit spacing only."""
    if node.children:
        return False
    if node.type not in {NodeType.CONTAINER, NodeType.STACK, NodeType.ROW}:
        return False
    width = node.sizing.width
    height = node.sizing.height
    width_px = float(width) if width is not None else 0.0
    height_px = float(height) if height is not None else 0.0
    if width_px <= 0.0 and height_px <= 0.0:
        return False
    if 0.0 < height_px <= _MAX_SPACER_AXIS_PX:
        return True
    if 0.0 < width_px <= _MAX_SPACER_AXIS_PX and height_px <= 0.0:
        return True
    return False


def dimensioned_spacer_widget_expr(node: CleanDesignTreeNode) -> str | None:
    """Emit a finite ``SizedBox`` spacer when bounds are present."""
    if not layout_fact_dimensioned_spacer_leaf(node):
        return None
    parts: list[str] = []
    width = node.sizing.width
    height = node.sizing.height
    if width is not None and float(width) > 0.0:
        parts.append(f"width: {format_geometry_literal(float(width))}")
    if height is not None and float(height) > 0.0:
        parts.append(f"height: {format_geometry_literal(float(height))}")
    if not parts:
        return None
    return f"SizedBox({', '.join(parts)})"
