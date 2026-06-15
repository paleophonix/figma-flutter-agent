"""Sizing and alignment extraction helpers."""

from __future__ import annotations

from typing import Any, Literal

from figma_flutter_agent.parser.numeric_rounding import (
    round_geometry,
    round_padding,
)
from figma_flutter_agent.schemas import (
    Alignment,
    Padding,
    Sizing,
    SizingMode,
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
    node_type: Any,
    sizing: Sizing,
    *,
    stack_placement: Any | None,
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
    from figma_flutter_agent.schemas import NodeType

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


def _visible_figma_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        child
        for child in (node.get("children") or [])
        if isinstance(child, dict) and child.get("visible") is not False
    ]


def adjust_sizing_for_visible_children(
    node: dict[str, Any],
    sizing: Sizing,
    *,
    visible_children: list[dict[str, Any]] | None = None,
) -> Sizing:
    """Recompute HUG axis sizes from visible children when hidden nodes were dropped.

    Figma ``absoluteBoundingBox`` on a parent can still reflect ``visible: false`` children.
    After the parser omits hidden nodes, shrink HUG width/height to the visible subtree extent.

    Args:
        node: Raw Figma frame node.
        sizing: Sizing extracted from ``extract_sizing``.
        visible_children: Visible child dicts (defaults to filtering ``node["children"]``).

    Returns:
        Adjusted sizing when HUG axes can be recomputed; otherwise ``sizing`` unchanged.
    """
    children = visible_children if visible_children is not None else _visible_figma_children(node)
    if not children:
        return sizing
    padding = extract_padding(node)
    item_spacing = float(node.get("itemSpacing") or 0)
    layout_mode = node.get("layoutMode")
    updates: dict[str, Any] = {}

    if layout_mode == "VERTICAL" and sizing.height_mode == SizingMode.HUG:
        total = padding.top + padding.bottom
        for index, child in enumerate(children):
            bounds = child.get("absoluteBoundingBox") or {}
            height = bounds.get("height")
            if height is not None:
                total += float(height)
            if index < len(children) - 1:
                total += item_spacing
        if total > 0:
            updates["height"] = round_geometry(total)
            updates["height_mode"] = SizingMode.FIXED

    if layout_mode == "HORIZONTAL" and sizing.width_mode == SizingMode.HUG:
        total = padding.left + padding.right
        for index, child in enumerate(children):
            bounds = child.get("absoluteBoundingBox") or {}
            width = bounds.get("width")
            if width is not None:
                total += float(width)
            if index < len(children) - 1:
                total += item_spacing
        if total > 0:
            updates["width"] = round_geometry(total)
            updates["width_mode"] = SizingMode.FIXED

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
            width_mode = SizingMode.FILL
        elif parent_mode == "VERTICAL":
            height_mode = SizingMode.FILL
    width = bounds.get("width")
    height = bounds.get("height")
    min_width = node.get("minWidth")
    max_width = node.get("maxWidth")
    min_height = node.get("minHeight")
    max_height = node.get("maxHeight")
    return Sizing(
        width_mode=width_mode,
        height_mode=height_mode,
        width=round_geometry(float(width)) if width is not None else None,
        height=round_geometry(float(height)) if height is not None else None,
        min_width=round_geometry(float(min_width)) if min_width is not None else None,
        max_width=round_geometry(float(max_width)) if max_width is not None else None,
        min_height=(round_geometry(float(min_height)) if min_height is not None else None),
        max_height=(round_geometry(float(max_height)) if max_height is not None else None),
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
