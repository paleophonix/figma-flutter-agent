"""Figma clean-tree → Flutter flex wrap policy (constraints down, sizes up)."""

from __future__ import annotations

import re
from collections.abc import Callable
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


def _column_subtree_needs_cross_stretch(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``Column`` must stretch children to avoid clipping FILL rows."""
    if node.sizing.width_mode == SizingMode.FILL:
        return True
    if node.type == NodeType.ROW:
        for child in node.children:
            if resolve_flex_wrap(parent_type=NodeType.ROW, node=child) == FlexWrapKind.EXPANDED:
                return True
    for child in node.children:
        if _column_subtree_needs_cross_stretch(child):
            return True
    return False


_TIGHT_CHIP_ROW_MAX_USABLE_SPAN = 80.0
_INTRINSIC_ROW_CHILD_MAX_SPAN = 120.0


def row_is_tight_horizontal_chip(parent: CleanDesignTreeNode) -> bool:
    """Return True when a ``Row`` hosts pill/badge copy in a bounded horizontal span."""
    if parent.type != NodeType.ROW:
        return False
    span = _row_usable_main_span(parent)
    if span is None:
        return False
    return span <= _TIGHT_CHIP_ROW_MAX_USABLE_SPAN


def row_is_tight_horizontal_pill_label(parent: CleanDesignTreeNode) -> bool:
    """Return True when a tight ``Row`` is a pill label host (not a square glyph badge)."""
    if not row_is_tight_horizontal_chip(parent):
        return False
    height = parent.sizing.height
    if height is not None and height > 0 and height <= 30.0:
        return True
    if parent.padding is not None:
        pad_lr = float(parent.padding.left or 0) + float(parent.padding.right or 0)
        return pad_lr > 0
    return False


def _row_usable_main_span(parent: CleanDesignTreeNode) -> float | None:
    """Return the ROW main-axis span after horizontal padding."""
    if parent.type != NodeType.ROW:
        return None
    span = parent.sizing.width
    if (span is None or span <= 0) and parent.geometry_frame is not None:
        span = parent.geometry_frame.intrinsic_size.width
    if span is None or span <= 0:
        return None
    if parent.padding is not None:
        span -= float(parent.padding.left or 0.0) + float(parent.padding.right or 0.0)
    return max(0.0, float(span))


def _child_main_span(child: CleanDesignTreeNode) -> float | None:
    """Return a child's planned main-axis span for ROW flex allocation."""
    span = child.sizing.width
    if (span is None or span <= 0) and child.geometry_frame is not None:
        span = child.geometry_frame.intrinsic_size.width
    if span is None or span <= 0:
        return None
    return float(span)


def _row_child_keeps_intrinsic_width(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """True when a bounded ROW child should not receive ``Flexible``/``Expanded``."""
    if parent_node is None or parent_node.type != NodeType.ROW:
        return False
    if node.sizing.width_mode not in {SizingMode.FIXED, SizingMode.HUG}:
        return False
    span = _child_main_span(node)
    if span is None or span <= 0 or span > _INTRINSIC_ROW_CHILD_MAX_SPAN:
        return False
    if node.type in {
        NodeType.BUTTON,
        NodeType.CONTAINER,
        NodeType.IMAGE,
        NodeType.VECTOR,
        NodeType.INPUT,
        NodeType.CARD,
    }:
        return True
    if node.type == NodeType.ROW:
        return True
    return False


def _should_expand_sole_undersized_row_child(
    parent_node: CleanDesignTreeNode,
    node: CleanDesignTreeNode,
) -> bool:
    """True when a sole HUG/FIXED child should grow to fill a wider FILL ROW."""
    from figma_flutter_agent.generator.geometry.affine import geom_epsilon

    if parent_node.type != NodeType.ROW:
        return False
    if parent_node.sizing.width_mode != SizingMode.FILL:
        return False
    if len(parent_node.children) != 1 or parent_node.children[0].id != node.id:
        return False
    if node.type not in {NodeType.ROW, NodeType.COLUMN}:
        return False
    if node.sizing.width_mode not in {SizingMode.FIXED, SizingMode.HUG}:
        return False
    if node.sizing.height_mode == SizingMode.FILL:
        return False
    parent_span = _row_usable_main_span(parent_node)
    child_span = _child_main_span(node)
    if parent_span is None or child_span is None:
        return False
    return child_span < parent_span - geom_epsilon()


def _column_is_text_primary(node: CleanDesignTreeNode) -> bool:
    """True when a COLUMN's visible content is predominantly TEXT."""
    if node.type != NodeType.COLUMN or not node.children:
        return False
    if len(node.children) == 1 and node.children[0].type == NodeType.TEXT:
        return True
    return all(child.type == NodeType.TEXT for child in node.children)


_TIGHT_STACK_TEXT_MAX_HEIGHT = 28.0


def column_is_tight_stack_text_host(node: CleanDesignTreeNode) -> bool:
    """True for metadata columns pinned inside a short absolute ``Stack`` slot."""
    if not _column_is_text_primary(node):
        return False
    if node.stack_placement is None:
        return False
    height = node.stack_placement.height
    if height is None or height <= 0:
        height = node.sizing.height
    if height is None or height <= 0:
        return False
    return float(height) <= _TIGHT_STACK_TEXT_MAX_HEIGHT


def text_host_is_tight_positioned(node: CleanDesignTreeNode) -> bool:
    """True when TEXT must not receive extra delta-top padding beyond its slot."""
    if node.type != NodeType.TEXT:
        return False
    height = node.sizing.height
    if (height is None or height <= 0) and node.stack_placement is not None:
        height = node.stack_placement.height
    if height is None or height <= 0:
        return False
    return float(height) <= _TIGHT_STACK_TEXT_MAX_HEIGHT


def column_in_bounded_positioned_host(node: CleanDesignTreeNode) -> bool:
    """True when a ``Column`` is pinned inside a fixed-height ``Stack`` slot."""
    if node.type != NodeType.COLUMN or node.stack_placement is None:
        return False
    height = node.stack_placement.height
    if height is None or height <= 0:
        height = node.sizing.height
    return height is not None and height > 0


def column_cross_to_align_expr(cross: str | None) -> str:
    """Map Figma column cross-axis to a single-child ``Align`` expression."""
    mapping = {
        "end": "Alignment.centerRight",
        "center": "Alignment.center",
        "stretch": "Alignment.centerRight",
        "start": "Alignment.centerLeft",
    }
    return mapping.get(cross or "start", "Alignment.centerLeft")


def emit_flexible_loose(widget: str, *, flex: int = 0) -> str:
    """Emit ``Flexible`` with explicit flex factor (default non-growing)."""
    if flex == 0:
        return f"Flexible(fit: FlexFit.loose, flex: 0, child: {widget})"
    return f"Flexible(fit: FlexFit.loose, child: {widget})"


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
    if (
        node.type == NodeType.COLUMN
        and parent_type == NodeType.ROW
        and (
            node.sizing.width_mode == SizingMode.FILL
            or _column_needs_expanded_under_row(node)
        )
    ):
        # FILL-width columns in a Row must stretch children horizontally. Figma
        # ``counterAxisAlignItems: CENTER`` would hug children and clip copy.
        return _resolve_column_cross_axis(
            node,
            parent_type=parent_type,
            default="CrossAxisAlignment.stretch",
        )
    cross_axis = _CROSS_AXIS_DART.get(cross, "CrossAxisAlignment.start")
    if (
        node.type == NodeType.COLUMN
        and cross_axis == "CrossAxisAlignment.center"
        and _column_subtree_needs_cross_stretch(node)
    ):
        cross_axis = "CrossAxisAlignment.stretch"
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
            if default == "CrossAxisAlignment.start":
                return "CrossAxisAlignment.stretch"
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
        if parent_node is not None and _should_expand_sole_undersized_row_child(
            parent_node, node
        ):
            return FlexWrapKind.EXPANDED
        if _row_child_keeps_intrinsic_width(node, parent_node):
            return FlexWrapKind.NONE
        if width_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if node.type == NodeType.ROW and _row_hosts_horizontal_flex_children(node):
            if height_mode == SizingMode.FILL and width_mode != SizingMode.FILL:
                return FlexWrapKind.NONE
            if (
                parent_node is not None
                and len(parent_node.children) > 1
                and width_mode in {SizingMode.FIXED, SizingMode.HUG}
            ):
                from figma_flutter_agent.generator.geometry.affine import geom_epsilon

                parent_span = _row_usable_main_span(parent_node)
                child_span = _child_main_span(node)
                if (
                    parent_span is not None
                    and child_span is not None
                    and child_span < parent_span - geom_epsilon()
                ):
                    return FlexWrapKind.FLEXIBLE_LOOSE
            return FlexWrapKind.EXPANDED
        if node.type == NodeType.COLUMN and _column_needs_expanded_under_row(node):
            return FlexWrapKind.EXPANDED
        if width_mode in {SizingMode.FIXED, SizingMode.HUG} and node.type == NodeType.TEXT:
            if parent_node is not None and row_is_tight_horizontal_pill_label(
                parent_node
            ):
                return FlexWrapKind.EXPANDED
            if (
                parent_node is not None
                and len(parent_node.children) > 1
            ):
                parent_span = _row_usable_main_span(parent_node)
                if (
                    parent_span is not None
                    and parent_span <= _INTRINSIC_ROW_CHILD_MAX_SPAN
                ):
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
    from figma_flutter_agent.generator.layout.widget import _node_layout_size
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
    from figma_flutter_agent.generator.layout.responsive import responsive_host_width_literal

    width_lit = responsive_host_width_literal(width)
    height_lit = format_geometry_literal(height)
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    def _bound(inner: str) -> str:
        inner_trimmed = inner.lstrip()
        inner_prefix = inner[: len(inner) - len(inner_trimmed)]
        if inner_trimmed.startswith("SizedBox("):
            child_marker = ", child: "
            marker_idx = inner_trimmed.find(child_marker)
            if marker_idx < 0:
                return inner
            head = inner_trimmed[:marker_idx]
            tail = inner_trimmed[marker_idx:]
            if ", height:" in head:
                return inner
            if "width:" not in head:
                return inner
            return f"{inner_prefix}{head}, height: {height_lit}{tail}"
        return (
            f"{inner_prefix}SizedBox("
            f"width: {width_lit}, "
            f"height: {height_lit}, "
            f"child: {inner})"
        )

    return hoist_flex_parent_data(_bound, widget)


def relax_row_cross_stretch_when_unbounded(
    widget: str,
    *,
    node_type: NodeType,
) -> str:
    """``Row`` + ``CrossAxisAlignment.stretch`` requires a bounded height (Flutter flex law)."""
    if node_type != NodeType.ROW:
        return widget
    trimmed = widget.lstrip()
    if not trimmed.startswith("Row("):
        return widget
    children_idx = trimmed.find("children:")
    if children_idx < 0:
        return widget
    head = trimmed[:children_idx]
    if "crossAxisAlignment: CrossAxisAlignment.stretch" not in head:
        return widget
    prefix = widget[: len(widget) - len(trimmed)]
    relaxed_head = head.replace(
        "crossAxisAlignment: CrossAxisAlignment.stretch",
        "crossAxisAlignment: CrossAxisAlignment.start",
        1,
    )
    return prefix + relaxed_head + trimmed[children_idx:]


def wrap_column_child_width_fill(widget: str, node: CleanDesignTreeNode) -> str:
    """Wrap a COLUMN width-FILL child without leaving a ``Row`` height unbounded."""
    from figma_flutter_agent.generator.layout.responsive import responsive_host_width_literal

    width = node.sizing.width
    height = node.sizing.height
    width_lit = responsive_host_width_literal(
        width,
        width_mode=node.sizing.width_mode,
    )
    if height is not None and height > 0 and _flex_child_should_bind_fixed_height(node):
        return (
            f"SizedBox(width: {width_lit}, "
            f"height: {format_geometry_literal(height)}, "
            f"child: {widget})"
        )
    relaxed = relax_row_cross_stretch_when_unbounded(widget, node_type=node.type)
    return f"SizedBox(width: {width_lit}, child: {relaxed})"


def _extract_balanced_prefix_child(source: str, child_start: int) -> str | None:
    """Return the balanced child expression starting at ``child_start``."""
    depth = 0
    for index in range(child_start, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return source[child_start:index]
            depth -= 1
    return None


def _unwrap_flex_parent_data_wrapper(widget: str) -> tuple[str, str] | None:
    """Return ``(wrapper_prefix, inner)`` for a top-level Expanded/Flexible wrapper."""
    trimmed = widget.lstrip()
    for marker in (
        "Expanded(child: ",
        "Flexible(fit: FlexFit.loose, flex: 0, child: ",
        "Flexible(fit: FlexFit.loose, child: ",
        "Flexible(child: ",
        "const Expanded(child: ",
        "const Flexible(fit: FlexFit.loose, flex: 0, child: ",
        "const Flexible(fit: FlexFit.loose, child: ",
        "const Flexible(child: ",
    ):
        if trimmed.startswith(marker):
            inner = _extract_balanced_prefix_child(trimmed, len(marker))
            if inner is not None:
                return marker, inner
    return None


def hoist_flex_parent_data(wrapper: Callable[[str], str], widget: str) -> str:
    """Apply ``wrapper`` inside ``Expanded``/``Flexible`` when already present."""
    unwrapped = _unwrap_flex_parent_data_wrapper(widget)
    if unwrapped is None:
        return wrapper(widget)
    marker, inner = unwrapped
    return f"{marker}{wrapper(inner)})"


def _replace_infinite_height_literal(widget: str, height_lit: str) -> str:
    """Swap ``height: double.infinity`` for a finite Figma height literal."""
    return widget.replace("height: double.infinity", f"height: {height_lit}")


def _pin_row_cross_axis_height_inner(inner: str, height_lit: str) -> str:
    """Add a finite cross-axis height inside a ROW flex child expression."""
    trimmed = inner.lstrip()
    prefix = inner[: len(inner) - len(trimmed)]
    if trimmed.startswith("SizedBox("):
        child_marker = ", child: "
        marker_idx = trimmed.find(child_marker)
        if marker_idx > 0 and ", height:" not in trimmed[:marker_idx]:
            head = trimmed[:marker_idx]
            tail = trimmed[marker_idx:]
            if "width:" in head:
                return f"{prefix}{head}, height: {height_lit}{tail}"
    return f"{prefix}SizedBox(height: {height_lit}, child: {inner})"


def bind_row_cross_axis_height(node: CleanDesignTreeNode, widget: str) -> str:
    """Pin ROW cross-axis extent; infinite height crashes in scroll/flex hosts."""
    height = node.sizing.height
    if height is None or height <= 0:
        return widget
    height_lit = format_geometry_literal(height)
    if "height: double.infinity" in widget:
        return _replace_infinite_height_literal(widget, height_lit)
    if node.type == NodeType.COLUMN and _column_is_text_primary(node):
        return hoist_flex_parent_data(
            lambda inner: (
                f"ConstrainedBox("
                f"constraints: BoxConstraints(minHeight: {height_lit}), "
                f"child: {inner})"
            ),
            widget,
        )
    return hoist_flex_parent_data(
        lambda inner: _pin_row_cross_axis_height_inner(inner, height_lit),
        widget,
    )


def prepare_flex_child_extents(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Extent pins on inner content before ``Expanded``/``Flexible`` wrappers."""
    working = widget
    height = node.sizing.height
    if height is not None and height > 0 and "height: double.infinity" in working:
        working = _replace_infinite_height_literal(
            working,
            format_geometry_literal(height),
        )
    compact = _bound_compact_icon_button(node, working)
    if compact is not None:
        working = compact
    return working


def post_flex_layout_slot_extents(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Extent pins after planner flex wraps — must stay outside ``Flexible``/``Expanded``."""
    working = widget
    if parent_type == NodeType.COLUMN and node.type == NodeType.STACK:
        bounded = _bound_stack_sized_box(node, working)
        if bounded is not None:
            working = bounded
    if parent_type == NodeType.ROW:
        working = bind_row_cross_axis_height(node, working)
    return working


def finalize_flex_child_extents(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Universal extent binding (pre- and post-flex phases)."""
    working = prepare_flex_child_extents(
        widget,
        parent_type=parent_type,
        node=node,
    )
    return post_flex_layout_slot_extents(
        working,
        parent_type=parent_type,
        node=node,
    )


def _bound_compact_icon_button(node: CleanDesignTreeNode, widget: str) -> str | None:
    """Pin circular icon buttons to Figma bounds before flex loose-wrap."""
    from figma_flutter_agent.parser.interaction import looks_like_compact_icon_action_button

    if node.type != NodeType.BUTTON or not looks_like_compact_icon_action_button(node):
        return None
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    width_lit = format_geometry_literal(width)
    height_lit = format_geometry_literal(height)
    return (
        f"SizedBox("
        f"width: {width_lit}, "
        f"height: {height_lit}, "
        f"child: {widget})"
    )


def _flex_column_open_index(widget: str) -> int | None:
    """Return the index of the outermost ``Column(`` in a flex child expression."""
    match = re.search(r"\bColumn\(", widget)
    return match.start() if match else None


def _coerce_column_cross_stretch_for_row_expand(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Stretch FILL-width ``Column`` children when wrapped in ``Expanded`` under ``Row``."""
    if parent_type != NodeType.ROW or node.type != NodeType.COLUMN:
        return widget
    if node.sizing.width_mode != SizingMode.FILL and not _column_needs_expanded_under_row(
        node
    ):
        return widget
    column_idx = _flex_column_open_index(widget)
    if column_idx is None:
        return widget
    if "crossAxisAlignment: CrossAxisAlignment.stretch" in widget[column_idx:]:
        return widget
    prefix, column_expr = widget[:column_idx], widget[column_idx:]
    patched = re.sub(
        r"crossAxisAlignment:\s*CrossAxisAlignment\.\w+",
        "crossAxisAlignment: CrossAxisAlignment.stretch",
        column_expr,
        count=1,
    )
    return prefix + patched


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
        widget = _coerce_column_cross_stretch_for_row_expand(
            widget,
            parent_type=parent_type,
            node=node,
        )
        return f"Expanded(child: {widget})"
    if kind == FlexWrapKind.FLEXIBLE_LOOSE:
        return emit_flexible_loose(widget)
    if kind == FlexWrapKind.SIZED_BOX_WIDTH:
        return wrap_column_child_width_fill(widget, node)
    return widget
