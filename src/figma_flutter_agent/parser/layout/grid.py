"""Grid and scroll extraction helpers."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import NodeType, ScrollAxis


def extract_scroll_axis(node: dict[str, Any]) -> ScrollAxis:
    """Map Figma overflowDirection to a scroll axis for ListView codegen."""
    direction = node.get("overflowDirection")
    if direction == "VERTICAL_SCROLLING":
        return "vertical"
    if direction == "HORIZONTAL_SCROLLING":
        return "horizontal"
    if direction == "BOTH":
        return "both"
    return "none"


def extract_grid_column_count(node: dict[str, Any], *, child_count: int) -> int:
    """Return column count for a Figma GRID auto-layout frame."""
    raw = node.get("gridColumnCount")
    if isinstance(raw, (int, float)) and raw >= 1:
        return int(raw)
    if child_count <= 1:
        return 1
    return min(child_count, 2)


def extract_grid_gaps(node: dict[str, Any]) -> tuple[float, float]:
    """Return (row gap, column gap) for a Figma GRID auto-layout frame."""
    spacing = round_geometry(float(node.get("itemSpacing") or 0)) or 0.0
    row_gap = node.get("gridRowGap")
    column_gap = node.get("gridColumnGap")
    row = float(row_gap) if row_gap is not None else spacing
    column = float(column_gap) if column_gap is not None else spacing
    row_r = round_geometry(row)
    column_r = round_geometry(column)
    return (
        row_r if row_r is not None else 0.0,
        column_r if column_r is not None else 0.0,
    )


def infer_container_type(node: dict[str, Any]) -> NodeType:
    """Infer semantic container type from Figma layout metadata."""
    if node.get("type") == "GROUP":
        return NodeType.STACK
    layout_mode = node.get("layoutMode", "NONE")
    if layout_mode == "GRID":
        return NodeType.GRID
    if node.get("layoutWrap") == "WRAP" and layout_mode in {"HORIZONTAL", "VERTICAL"}:
        return NodeType.WRAP
    if layout_mode == "HORIZONTAL":
        return NodeType.ROW
    if layout_mode == "VERTICAL":
        return NodeType.COLUMN
    if layout_mode == "NONE":
        return NodeType.STACK
    return NodeType.CONTAINER
