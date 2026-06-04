"""Figma clean-tree → Flutter flex wrap policy (constraints down, sizes up)."""

from __future__ import annotations

from enum import StrEnum

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode


class FlexWrapKind(StrEnum):
    """How to wrap a flex child before it is emitted or reconciled."""

    NONE = "none"
    EXPANDED = "expanded"
    FLEXIBLE_LOOSE = "flexible_loose"
    SIZED_BOX_WIDTH = "sized_box_width"


_FLEX_RIGID_CHILD_TYPES = frozenset(
    {
        NodeType.TEXT,
        NodeType.CONTAINER,
        NodeType.IMAGE,
        NodeType.VECTOR,
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CARD,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.DROPDOWN,
    }
)


def _row_hosts_horizontal_flex_children(node: CleanDesignTreeNode) -> bool:
    """True when a nested ``Row`` will emit ``Expanded`` / ``Flexible`` on its main axis."""
    if node.type != NodeType.ROW:
        return False
    for child in node.children:
        child_wrap = resolve_flex_wrap(parent_type=NodeType.ROW, node=child)
        if child_wrap in {FlexWrapKind.EXPANDED, FlexWrapKind.FLEXIBLE_LOOSE}:
            return True
        if child.type == NodeType.ROW and _row_hosts_horizontal_flex_children(child):
            return True
    return False


def _column_needs_expanded_under_row(node: CleanDesignTreeNode) -> bool:
    """True when a ``Column`` in a ``Row`` needs a bounded width (``Expanded`` on main axis)."""
    if node.type != NodeType.COLUMN:
        return False
    if node.sizing.width_mode == SizingMode.FILL:
        return True
    if node.sizing.height_mode == SizingMode.FILL:
        return True
    if node.alignment.cross == "stretch":
        return True
    for child in node.children:
        if resolve_flex_wrap(parent_type=NodeType.COLUMN, node=child) == FlexWrapKind.SIZED_BOX_WIDTH:
            return True
    return False


_CROSS_AXIS_DART = {
    "start": "CrossAxisAlignment.start",
    "end": "CrossAxisAlignment.end",
    "center": "CrossAxisAlignment.center",
    "spaceBetween": "CrossAxisAlignment.center",
    "stretch": "CrossAxisAlignment.stretch",
    "baseline": "CrossAxisAlignment.baseline",
}


def resolve_cross_axis_alignment(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    cross: str,
) -> str:
    """Map Figma cross alignment to a Flutter value that is valid under ``parent_type``."""
    cross_axis = _CROSS_AXIS_DART.get(cross, "CrossAxisAlignment.start")
    if cross_axis != "CrossAxisAlignment.stretch":
        return cross_axis
    if node.type == NodeType.ROW:
        return _resolve_row_cross_axis(node, parent_type=parent_type, default=cross_axis)
    if node.type == NodeType.COLUMN:
        return _resolve_column_cross_axis(node, parent_type=parent_type, default=cross_axis)
    return cross_axis


def _resolve_row_cross_axis(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    default: str,
) -> str:
    """``Row`` cross-axis (vertical) stretch requires a bounded max height from the parent."""
    height = node.sizing.height
    has_pixel_height = height is not None and height > 0
    if parent_type == NodeType.ROW:
        return "CrossAxisAlignment.start"
    if parent_type == NodeType.COLUMN:
        if node.sizing.height_mode == SizingMode.FILL:
            return default
        if has_pixel_height:
            return default
        return "CrossAxisAlignment.start"
    return default


def _resolve_column_cross_axis(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    default: str,
) -> str:
    """``Column`` cross-axis (horizontal) stretch requires a bounded max width from the parent."""
    width = node.sizing.width
    has_pixel_width = width is not None and width > 0
    if parent_type == NodeType.ROW:
        if node.sizing.width_mode == SizingMode.FILL or _column_needs_expanded_under_row(node):
            return default
        return "CrossAxisAlignment.start"
    if parent_type == NodeType.COLUMN:
        if node.sizing.width_mode == SizingMode.FILL:
            return default
        if has_pixel_width:
            return default
        return "CrossAxisAlignment.start"
    return default


def resolve_flex_wrap(
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> FlexWrapKind:
    """Return the flex wrapper required for ``node`` under ``parent_type``."""
    if parent_type is None:
        return FlexWrapKind.NONE

    width_mode = node.sizing.width_mode
    height_mode = node.sizing.height_mode

    if parent_type == NodeType.ROW:
        if width_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if node.type == NodeType.ROW and _row_hosts_horizontal_flex_children(node):
            return FlexWrapKind.EXPANDED
        if node.type == NodeType.COLUMN and _column_needs_expanded_under_row(node):
            return FlexWrapKind.EXPANDED
        if width_mode in {SizingMode.FIXED, SizingMode.HUG} and node.type in _FLEX_RIGID_CHILD_TYPES:
            return FlexWrapKind.FLEXIBLE_LOOSE

    if parent_type == NodeType.COLUMN:
        if height_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if width_mode == SizingMode.FILL:
            return FlexWrapKind.SIZED_BOX_WIDTH

    return FlexWrapKind.NONE


def _bound_stack_sized_box(node: CleanDesignTreeNode, widget: str) -> str | None:
    """Give ``Stack`` children of ``Column`` finite constraints (Flutter flex law)."""
    if widget.lstrip().startswith("SizedBox("):
        return None
    from figma_flutter_agent.generator.layout_widget import _node_layout_size
    from figma_flutter_agent.parser.interaction import (
        looks_like_back_nav_stack,
        looks_like_skip_control_stack,
    )

    placement = node.stack_placement
    width, height = _node_layout_size(node, placement)
    if width is None or width <= 0:
        return None
    if height is None or height <= 0:
        if looks_like_back_nav_stack(node) or looks_like_skip_control_stack(node):
            side = max(float(width), 48.0)
            width = height = side
        else:
            return None
    return (
        f"SizedBox("
        f"width: {format_geometry_literal(width)}, "
        f"height: {format_geometry_literal(height)}, "
        f"child: {widget})"
    )


def relax_row_cross_stretch_when_unbounded(
    widget: str,
    *,
    node_type: NodeType,
) -> str:
    """``Row`` + ``CrossAxisAlignment.stretch`` requires a bounded height (Flutter flex law)."""
    if node_type != NodeType.ROW:
        return widget
    if not widget.lstrip().startswith("Row("):
        return widget
    return widget.replace(
        "crossAxisAlignment: CrossAxisAlignment.stretch",
        "crossAxisAlignment: CrossAxisAlignment.start",
        1,
    )


def wrap_column_child_width_fill(widget: str, node: CleanDesignTreeNode) -> str:
    """Wrap a COLUMN width-FILL child without leaving a ``Row`` height unbounded."""
    height = node.sizing.height
    if height is not None and height > 0:
        return (
            f"SizedBox(width: double.infinity, "
            f"height: {format_geometry_literal(height)}, "
            f"child: {widget})"
        )
    relaxed = relax_row_cross_stretch_when_unbounded(widget, node_type=node.type)
    return f"SizedBox(width: double.infinity, child: {relaxed})"


def apply_flex_wrap_to_widget(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Wrap a rendered widget expression according to flex policy."""
    if parent_type == NodeType.COLUMN and node.type == NodeType.STACK:
        bounded = _bound_stack_sized_box(node, widget)
        if bounded is not None:
            return bounded
    kind = resolve_flex_wrap(parent_type=parent_type, node=node)
    if kind == FlexWrapKind.NONE:
        return widget
    if kind == FlexWrapKind.EXPANDED:
        return f"Expanded(child: {widget})"
    if kind == FlexWrapKind.FLEXIBLE_LOOSE:
        return f"Flexible(fit: FlexFit.loose, child: {widget})"
    if kind == FlexWrapKind.SIZED_BOX_WIDTH:
        return wrap_column_child_width_fill(widget, node)
    return widget
