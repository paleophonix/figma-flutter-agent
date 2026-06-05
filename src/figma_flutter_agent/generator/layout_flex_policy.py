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
        if (
            resolve_flex_wrap(parent_type=NodeType.COLUMN, node=child)
            == FlexWrapKind.SIZED_BOX_WIDTH
        ):
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

_MAIN_AXIS_DART = {
    "start": "MainAxisAlignment.start",
    "end": "MainAxisAlignment.end",
    "center": "MainAxisAlignment.center",
    "spaceBetween": "MainAxisAlignment.spaceBetween",
    "stretch": "MainAxisAlignment.spaceBetween",
    "baseline": "MainAxisAlignment.start",
}


def resolve_main_axis_alignment(
    node: CleanDesignTreeNode,
    *,
    scroll_content_root: bool = False,
) -> str:
    """Map Figma main-axis alignment to Flutter, with scroll-safe coercion."""
    main = node.alignment.main or "start"
    if main != "center":
        return _MAIN_AXIS_DART.get(main, "MainAxisAlignment.start")
    if scroll_content_root:
        return "MainAxisAlignment.start"
    if (
        node.type == NodeType.COLUMN
        and len(node.children) > 1
        and node.sizing.height_mode != SizingMode.FILL
        and (node.sizing.height is None or node.sizing.height <= 0)
    ):
        return "MainAxisAlignment.start"
    return "MainAxisAlignment.center"


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
        return _resolve_row_cross_axis(
            node, parent_type=parent_type, default=cross_axis
        )
    if node.type == NodeType.COLUMN:
        return _resolve_column_cross_axis(
            node, parent_type=parent_type, default=cross_axis
        )
    return cross_axis


def _row_hosts_title_text(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` subtree carries heading/body copy beside chrome."""
    if node.type == NodeType.TEXT:
        return True
    for child in node.children:
        if _row_hosts_title_text(child):
            return True
    return False


def _row_hosts_compact_icon_with_text(node: CleanDesignTreeNode) -> bool:
    """Return True when a header ``Row`` mixes a circular icon button with title copy."""
    from figma_flutter_agent.parser.interaction import (
        looks_like_back_nav_stack,
        looks_like_compact_icon_action_button,
    )

    if node.type != NodeType.ROW:
        return False

    def _hosts_icon_button(item: CleanDesignTreeNode) -> bool:
        if looks_like_compact_icon_action_button(item) or looks_like_back_nav_stack(item):
            return True
        return any(_hosts_icon_button(child) for child in item.children)

    return _hosts_icon_button(node) and _row_hosts_title_text(node)


def _subtree_has_input(node: CleanDesignTreeNode) -> bool:
    """Return True when an ``INPUT`` appears anywhere under ``node``."""
    if node.type == NodeType.INPUT:
        return True
    return any(_subtree_has_input(child) for child in node.children)


def _is_form_field_group_column(node: CleanDesignTreeNode) -> bool:
    """Return True for label + field stacks that must grow past a Figma bbox height."""
    if node.type != NodeType.COLUMN:
        return False
    child_types = {child.type for child in node.children}
    if NodeType.TEXT in child_types and NodeType.INPUT in child_types:
        return True
    if NodeType.TEXT in child_types and len(node.children) > 1:
        return any(
            child.type
            in {NodeType.INPUT, NodeType.BUTTON, NodeType.COLUMN, NodeType.ROW}
            for child in node.children
        )
    return False


def _text_has_multiple_lines(node: CleanDesignTreeNode) -> bool:
    """Return True when Figma text content spans more than one line."""
    if node.type != NodeType.TEXT:
        return False
    raw = (node.text or "").strip()
    if not raw:
        return False
    return "\n" in raw or len(raw.splitlines()) > 1


def _row_hosts_stacked_column_peer(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` pairs a fixed bbox with a multi-child ``Column`` peer."""
    if node.type != NodeType.ROW:
        return False
    return any(
        child.type == NodeType.COLUMN and len(child.children) >= 2
        for child in node.children
    )


def _parent_row_has_bounded_height(parent_node: CleanDesignTreeNode | None) -> bool:
    """Return True when the flex parent ``Row`` pins a finite cross-axis height."""
    if parent_node is None or parent_node.type != NodeType.ROW:
        return False
    height = parent_node.sizing.height
    return height is not None and height > 0


def _column_peer_in_bounded_row(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True when a multi-child ``Column`` sits in a height-bounded ``Row``."""
    if node.type != NodeType.COLUMN or len(node.children) < 2:
        return False
    return _parent_row_has_bounded_height(parent_node)


def _flex_child_should_bind_fixed_height(node: CleanDesignTreeNode) -> bool:
    """Return True when a COLUMN width-fill child may also pin Figma frame height."""
    height = node.sizing.height
    if height is None or height <= 0:
        return False
    if node.sizing.height_mode == SizingMode.FILL:
        return True
    if node.type == NodeType.ROW and _row_hosts_stacked_column_peer(node):
        return False
    if _is_form_field_group_column(node):
        return False
    if node.type == NodeType.COLUMN and len(node.children) > 1:
        return False
    if node.type == NodeType.TEXT and _text_has_multiple_lines(node):
        return False
    if node.type == NodeType.COLUMN and len(node.children) == 1:
        if not _flex_child_should_bind_fixed_height(node.children[0]):
            return False
    if node.type == NodeType.CONTAINER and len(node.children) == 1:
        return _flex_child_should_bind_fixed_height(node.children[0])
    return True


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
        if has_pixel_height and _row_hosts_compact_icon_with_text(node):
            return "CrossAxisAlignment.center"
        if has_pixel_height and _row_hosts_title_text(node):
            return "CrossAxisAlignment.start"
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
        if (
            node.sizing.width_mode == SizingMode.FILL
            or _column_needs_expanded_under_row(node)
        ):
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
    parent_node: CleanDesignTreeNode | None = None,
) -> FlexWrapKind:
    """Return the flex wrapper required for ``node`` under ``parent_type``."""
    if parent_type is None:
        return FlexWrapKind.NONE

    width_mode = node.sizing.width_mode
    height_mode = node.sizing.height_mode
    bounded_row_peer = _column_peer_in_bounded_row(node, parent_node=parent_node)

    if parent_type == NodeType.ROW:
        if width_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if (
            width_mode == SizingMode.FIXED
            and node.sizing.width is not None
            and node.sizing.width > 0
        ):
            return FlexWrapKind.FLEXIBLE_LOOSE
        if node.type == NodeType.ROW and _row_hosts_horizontal_flex_children(node):
            return FlexWrapKind.EXPANDED
        if node.type == NodeType.COLUMN and _column_needs_expanded_under_row(node):
            return FlexWrapKind.EXPANDED
        if (
            width_mode in {SizingMode.FIXED, SizingMode.HUG}
            and node.type in _FLEX_RIGID_CHILD_TYPES
        ):
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
    width = node.sizing.width
    height = node.sizing.height
    if node.sizing.width_mode == SizingMode.FILL:
        width_lit = "double.infinity"
    elif width is not None and width > 0:
        width_lit = format_geometry_literal(width)
    else:
        width_lit = "double.infinity"
    if height is not None and height > 0 and _flex_child_should_bind_fixed_height(node):
        return (
            f"SizedBox(width: {width_lit}, "
            f"height: {format_geometry_literal(height)}, "
            f"child: {widget})"
        )
    relaxed = relax_row_cross_stretch_when_unbounded(widget, node_type=node.type)
    return f"SizedBox(width: {width_lit}, child: {relaxed})"


def _bound_compact_icon_button(node: CleanDesignTreeNode, widget: str) -> str | None:
    """Pin circular icon buttons to Figma bounds before flex loose-wrap."""
    from figma_flutter_agent.parser.interaction import looks_like_compact_icon_action_button

    if node.type != NodeType.BUTTON or not looks_like_compact_icon_action_button(node):
        return None
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return (
        f"SizedBox("
        f"width: {format_geometry_literal(width)}, "
        f"height: {format_geometry_literal(height)}, "
        f"child: {widget})"
    )


def apply_flex_wrap_to_widget(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Wrap a rendered widget expression according to flex policy."""
    compact_icon = _bound_compact_icon_button(node, widget)
    if compact_icon is not None:
        widget = compact_icon
    if parent_type == NodeType.COLUMN and node.type == NodeType.STACK:
        bounded = _bound_stack_sized_box(node, widget)
        if bounded is not None:
            return bounded
    kind = resolve_flex_wrap(
        parent_type=parent_type, node=node, parent_node=parent_node
    )
    if kind == FlexWrapKind.NONE:
        return widget
    if kind == FlexWrapKind.EXPANDED:
        return f"Expanded(child: {widget})"
    if kind == FlexWrapKind.FLEXIBLE_LOOSE:
        return f"Flexible(fit: FlexFit.loose, child: {widget})"
    if kind == FlexWrapKind.SIZED_BOX_WIDTH:
        return wrap_column_child_width_fill(widget, node)
    return widget
