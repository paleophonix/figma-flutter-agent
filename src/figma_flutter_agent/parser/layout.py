"""Auto Layout to semantic layout mapping helpers."""

from __future__ import annotations

from typing import Any, Literal, cast

from figma_flutter_agent.parser.numeric_rounding import (
    round_geometry,
    round_padding,
    round_stack_placement,
)
from figma_flutter_agent.schemas import (
    Alignment,
    HorizontalConstraint,
    NodeStyle,
    NodeType,
    Padding,
    ScrollAxis,
    Sizing,
    SizingMode,
    StackPlacement,
    VerticalConstraint,
)

_AlignValue = Literal["start", "end", "center", "spaceBetween", "stretch", "baseline"]
_ALIGN_MAP: dict[str, _AlignValue] = {
    "MIN": "start",
    "MAX": "end",
    "CENTER": "center",
    "SPACE_BETWEEN": "spaceBetween",
    "BASELINE": "baseline",
    "STRETCH": "stretch",
}


def map_alignment(value: str | None, default: _AlignValue = "start") -> _AlignValue:
    """Map Figma alignment enum to clean-tree alignment value."""
    if not value:
        return default
    return _ALIGN_MAP.get(value, default)


def map_sizing_mode(horizontal: str | None) -> SizingMode:
    """Map Figma sizing fields to a sizing mode."""
    if horizontal == "FILL":
        return SizingMode.FILL
    if horizontal == "FIXED":
        return SizingMode.FIXED
    return SizingMode.HUG


def extract_padding(node: dict[str, Any]) -> Padding:
    """Extract padding fields from a Figma node."""
    return round_padding(
        Padding(
            top=float(node.get("paddingTop") or 0),
            bottom=float(node.get("paddingBottom") or 0),
            left=float(node.get("paddingLeft") or 0),
            right=float(node.get("paddingRight") or 0),
        )
    )


def enforce_fixed_sizing_for_stack_and_button(
    node_type: NodeType,
    sizing: Sizing,
    *,
    stack_placement: StackPlacement | None,
    figma_node: dict[str, Any],
) -> Sizing:
    """Force FIXED width/height on STACK/BUTTON nodes that would otherwise HUG.

    Args:
        node_type: Clean-tree node type.
        sizing: Sizing extracted from the Figma node.
        stack_placement: Optional stack placement for the node.
        figma_node: Raw Figma node dictionary.

    Returns:
        Sizing with HUG modes rewritten to FIXED using placement or bounding box.
    """
    if node_type not in {NodeType.STACK, NodeType.BUTTON}:
        return sizing
    if sizing.width_mode != SizingMode.HUG and sizing.height_mode != SizingMode.HUG:
        return sizing

    bounds = figma_node.get("absoluteBoundingBox") or {}
    width = sizing.width
    height = sizing.height
    if stack_placement is not None:
        if width is None and stack_placement.width is not None:
            width = stack_placement.width
        if height is None and stack_placement.height is not None:
            height = stack_placement.height
    if width is None and bounds.get("width") is not None:
        width = round_geometry(float(bounds["width"]))
    if height is None and bounds.get("height") is not None:
        height = round_geometry(float(bounds["height"]))

    updates: dict[str, Any] = {}
    if sizing.width_mode == SizingMode.HUG:
        updates["width_mode"] = SizingMode.FIXED
        if width is not None:
            updates["width"] = width
    if sizing.height_mode == SizingMode.HUG:
        updates["height_mode"] = SizingMode.FIXED
        if height is not None:
            updates["height"] = height
    if not updates:
        return sizing
    return sizing.model_copy(update=updates)


def extract_sizing(node: dict[str, Any], parent: dict[str, Any] | None = None) -> Sizing:
    """Extract width and height sizing metadata from a Figma node."""
    bounds = node.get("absoluteBoundingBox") or {}
    width_mode = map_sizing_mode(node.get("layoutSizingHorizontal"))
    height_mode = map_sizing_mode(node.get("layoutSizingVertical"))
    if node.get("layoutGrow") == 1 and parent is not None:
        parent_mode = parent.get("layoutMode")
        if parent_mode == "HORIZONTAL":
            height_mode = SizingMode.FILL
        elif parent_mode == "VERTICAL":
            width_mode = SizingMode.FILL
    width = bounds.get("width")
    height = bounds.get("height")
    return Sizing(
        width_mode=width_mode,
        height_mode=height_mode,
        width=round_geometry(float(width)) if width is not None else None,
        height=round_geometry(float(height)) if height is not None else None,
    )


def extract_alignment(node: dict[str, Any]) -> Alignment:
    """Extract main and cross axis alignment from a Figma node."""
    return Alignment(
        main=map_alignment(node.get("primaryAxisAlignItems")),
        cross=map_alignment(node.get("counterAxisAlignItems"), "stretch"),
    )


def _constraint_axis(
    raw: str | None,
    *,
    allowed: set[str],
    default: str,
) -> str:
    if raw in allowed:
        return raw
    return default


def extract_stack_placement(
    node: dict[str, Any],
    parent: dict[str, Any],
) -> StackPlacement | None:
    """Extract classic frame constraints and edge distances for Stack children."""
    parent_mode = parent.get("layoutMode")
    is_classic_stack = parent_mode in (None, "NONE")
    is_auto_absolute = node.get("layoutPositioning") == "ABSOLUTE"
    if not is_classic_stack and not is_auto_absolute:
        return None

    node_bounds = node.get("absoluteBoundingBox") or {}
    parent_bounds = parent.get("absoluteBoundingBox") or {}
    node_width = float(node_bounds.get("width", 0))
    node_height = float(node_bounds.get("height", 0))
    parent_width = float(parent_bounds.get("width", 0))
    parent_height = float(parent_bounds.get("height", 0))
    left = float(node_bounds.get("x", 0)) - float(parent_bounds.get("x", 0))
    top = float(node_bounds.get("y", 0)) - float(parent_bounds.get("y", 0))
    right = parent_width - left - node_width
    bottom = parent_height - top - node_height

    constraints = node.get("constraints") or {}
    horizontal = _constraint_axis(
        constraints.get("horizontal"),
        allowed={"LEFT", "RIGHT", "CENTER", "LEFT_RIGHT", "SCALE"},
        default="LEFT",
    )
    vertical = _constraint_axis(
        constraints.get("vertical"),
        allowed={"TOP", "BOTTOM", "CENTER", "TOP_BOTTOM", "SCALE"},
        default="TOP",
    )
    if horizontal == "CENTER" and parent_width > 0:
        left = (parent_width - node_width) / 2
    if vertical == "CENTER" and parent_height > 0:
        top = (parent_height - node_height) / 2

    return round_stack_placement(
        StackPlacement(
            horizontal=cast(HorizontalConstraint, horizontal),
            vertical=cast(VerticalConstraint, vertical),
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            width=node_width if node_width > 0 else None,
            height=node_height if node_height > 0 else None,
        )
    )


def refine_text_stack_placement(
    node_type: NodeType,
    style: NodeStyle,
    parent_type: NodeType | None,
    placement: StackPlacement | None,
) -> StackPlacement | None:
    """Stretch centered text across parent Stack bounds so ``textAlign`` works."""
    if placement is None or node_type != NodeType.TEXT or parent_type != NodeType.STACK:
        return placement
    if style.text_align not in {"CENTER", "RIGHT"}:
        return placement
    return placement.model_copy(
        update={
            "horizontal": "LEFT_RIGHT",
            "left": 0.0,
            "right": 0.0,
        }
    )


def extract_layout_position(
    node: dict[str, Any],
    parent: dict[str, Any] | None,
) -> tuple[Literal["AUTO", "ABSOLUTE"], float, float]:
    """Extract absolute positioning metadata relative to the parent bounds."""
    if parent is not None:
        placement = extract_stack_placement(node, parent)
        if placement is not None:
            return "ABSOLUTE", placement.left, placement.top
    if node.get("layoutPositioning") != "ABSOLUTE":
        return "AUTO", 0.0, 0.0
    node_bounds = node.get("absoluteBoundingBox") or {}
    if parent is None:
        x = round_geometry(float(node_bounds.get("x", 0))) or 0.0
        y = round_geometry(float(node_bounds.get("y", 0))) or 0.0
        return "ABSOLUTE", x, y
    parent_bounds = parent.get("absoluteBoundingBox") or {}
    offset_x = round_geometry(
        float(node_bounds.get("x", 0)) - float(parent_bounds.get("x", 0))
    ) or 0.0
    offset_y = round_geometry(
        float(node_bounds.get("y", 0)) - float(parent_bounds.get("y", 0))
    ) or 0.0
    return "ABSOLUTE", offset_x, offset_y


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
