"""Flex wrap resolution and child extent management."""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal, round_geometry
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode


_INTRINSIC_ROW_CHILD_MAX_SPAN = 120.0


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


def resolve_flex_wrap(
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
) -> FlexWrapKind:
    """Return the flex wrapper required for ``node`` under ``parent_type``."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        _child_main_span,
        _column_peer_in_bounded_row,
        _row_child_keeps_intrinsic_width,
        _row_title_column_should_expand_beside_chip,
        _row_usable_main_span,
        _should_expand_sole_undersized_row_child,
        row_hosts_chip_beside_heading,
        row_hosts_equal_metric_cards,
        row_is_card_composite_body,
        row_is_numeric_counter_badge,
        row_is_space_between_text_metric_row,
        row_is_status_pill_badge,
        row_is_tight_horizontal_pill_label,
        row_is_toolbar_leading_title_row,
    )
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_needs_expanded_under_row,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        _row_hosts_horizontal_flex_children,
        row_is_icon_stepper_control_row,
    )
    from figma_flutter_agent.generator.layout.flex_policy.buttons import button_hosts_status_pill
    from figma_flutter_agent.generator.layout.flex_policy.text import text_in_card_metadata_rail

    if parent_type is None:
        return FlexWrapKind.NONE

    width_mode = node.sizing.width_mode
    height_mode = node.sizing.height_mode
    bounded_row_peer = _column_peer_in_bounded_row(node, parent_node=parent_node)

    if parent_type == NodeType.ROW:
        from figma_flutter_agent.generator.layout.common import (
            is_centered_glyph_badge,
            is_short_centered_glyph_text,
        )
        from figma_flutter_agent.parser.interaction import hosts_compact_checkbox_control

        if parent_node is not None and row_is_space_between_text_metric_row(parent_node):
            return FlexWrapKind.NONE
        if hosts_compact_checkbox_control(node):
            return FlexWrapKind.NONE
        if row_is_toolbar_leading_title_row(node):
            return FlexWrapKind.NONE
        if is_centered_glyph_badge(node) or is_short_centered_glyph_text(node):
            return FlexWrapKind.NONE
        if parent_node is not None and is_centered_glyph_badge(parent_node):
            return FlexWrapKind.NONE
        if text_in_card_metadata_rail(
            node,
            parent_node,
            parent_type=parent_type,
        ):
            return FlexWrapKind.NONE
        if (
            parent_node is not None
            and row_hosts_equal_metric_cards(parent_node)
            and node.type == NodeType.COLUMN
            and node.style.background_color
            and node.sizing.width_mode == SizingMode.FILL
        ):
            return FlexWrapKind.EXPANDED
        if parent_node is not None and row_hosts_chip_beside_heading(parent_node):
            return FlexWrapKind.NONE
        if node.type == NodeType.ROW and (
            row_is_tight_horizontal_pill_label(node)
            or row_is_status_pill_badge(node)
            or row_is_numeric_counter_badge(node)
        ):
            return FlexWrapKind.NONE
        if parent_node is not None and _should_expand_sole_undersized_row_child(
            parent_node, node
        ):
            return FlexWrapKind.EXPANDED
        if _row_child_keeps_intrinsic_width(node, parent_node):
            return FlexWrapKind.NONE
        if width_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if node.type == NodeType.ROW and _row_hosts_horizontal_flex_children(node):
            if (
                row_is_tight_horizontal_pill_label(node)
                or row_is_status_pill_badge(node)
                or row_is_numeric_counter_badge(node)
            ):
                return FlexWrapKind.NONE
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
        if node.type == NodeType.COLUMN and (
            _column_needs_expanded_under_row(node)
            or (
                parent_node is not None
                and _row_title_column_should_expand_beside_chip(parent_node, node)
            )
        ):
            return FlexWrapKind.EXPANDED
        if width_mode in {SizingMode.FIXED, SizingMode.HUG} and node.type == NodeType.TEXT:
            if parent_node is not None and (
                row_is_tight_horizontal_pill_label(parent_node)
                or row_is_status_pill_badge(parent_node)
            ):
                return FlexWrapKind.NONE
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
        if node.type == NodeType.ROW and row_hosts_chip_beside_heading(node):
            return FlexWrapKind.NONE
        if node.type == NodeType.BUTTON and button_hosts_status_pill(node):
            return FlexWrapKind.NONE
        if node.type == NodeType.ROW and row_is_icon_stepper_control_row(node):
            return FlexWrapKind.SIZED_BOX_WIDTH
        if height_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if width_mode == SizingMode.FILL:
            if node.type == NodeType.TEXT and (
                (node.style.text_align or "").upper() == "CENTER"
            ):
                return FlexWrapKind.NONE
            return FlexWrapKind.SIZED_BOX_WIDTH

    return FlexWrapKind.NONE


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


def hoist_flex_parent_data(wrapper: Callable[[str], str], widget: str) -> str:
    """Apply ``wrapper`` inside ``Expanded``/``Flexible`` when already present."""
    unwrapped = _unwrap_flex_parent_data_wrapper(widget)
    if unwrapped is None:
        return wrapper(widget)
    marker, inner = unwrapped
    return f"{marker}{wrapper(inner)})"


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


def apply_flex_wrap_to_widget(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Wrap a rendered widget expression according to flex policy."""
    from figma_flutter_agent.generator.layout.flex_policy.buttons import _bound_compact_icon_button
    from figma_flutter_agent.generator.layout.flex_policy.stack import _bound_stack_sized_box
    from figma_flutter_agent.generator.layout.flex_policy.alignment import emit_flexible_loose
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _coerce_column_cross_stretch_for_row_expand,
        wrap_column_child_width_fill,
    )

    compact_icon = _bound_compact_icon_button(node, widget)
    if compact_icon is not None:
        widget = compact_icon
    if parent_type in {NodeType.COLUMN, NodeType.CARD} and node.type == NodeType.STACK:
        bounded = _bound_stack_sized_box(node, widget, parent_type=parent_type)
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


def prepare_flex_child_extents(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Extent pins on inner content before ``Expanded``/``Flexible`` wrappers."""
    working = widget
    height = node.sizing.height
    if (
        height is not None
        and height > 0
        and _outer_sized_box_head_has_infinite_height(working)
    ):
        from figma_flutter_agent.generator.layout.widgets.layout import (
            _stack_has_bottom_anchored_child,
        )

        if node.type == NodeType.STACK and _stack_has_bottom_anchored_child(node):
            return working
        working = _replace_infinite_height_literal(
            working,
            format_geometry_literal(height),
        )
    return working


def post_flex_layout_slot_extents(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Extent pins after planner flex wraps — must stay outside ``Flexible``/``Expanded``."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import _bound_stack_sized_box
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_child_should_center_hug,
        column_center_hug_child_wrap,
        column_hosts_product_card_stepper,
    )
    from figma_flutter_agent.generator.layout.flex_policy.buttons import (
        button_hosts_status_pill,
        horizontal_chip_button_should_hug_width,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import row_is_status_pill_badge

    working = widget
    if node.type == NodeType.STACK and (
        parent_type == NodeType.COLUMN
        or (
            parent_type == NodeType.ROW
            and node.sizing.width_mode in {SizingMode.FIXED, SizingMode.HUG}
        )
    ):
        bounded = _bound_stack_sized_box(node, working, parent_type=parent_type)
        if bounded is not None:
            working = bounded
    if parent_type == NodeType.COLUMN and column_hosts_product_card_stepper(node):
        working = f"Align(alignment: Alignment.centerRight, child: {working})"
    elif (
        parent_type == NodeType.COLUMN
        and parent_node is not None
        and column_child_should_center_hug(parent_node, node)
    ):
        working = column_center_hug_child_wrap(parent_node, node, working)
    if parent_type == NodeType.COLUMN and button_hosts_status_pill(node):
        working = f"Align(alignment: Alignment.center, child: {working})"
    if parent_type == NodeType.WRAP and horizontal_chip_button_should_hug_width(node):
        working = f"IntrinsicWidth(child: {working})"
    from figma_flutter_agent.generator.layout.navigation.items import (
        column_is_compact_nav_tab,
    )

    if column_is_compact_nav_tab(node):
        working = (
            "ClipRect("
            "child: FittedBox("
            "fit: BoxFit.scaleDown, "
            "alignment: Alignment.center, "
            f"child: {working}))"
        )
    if parent_type == NodeType.ROW:
        working = bind_row_cross_axis_height(
            node,
            working,
            parent_row=parent_node,
        )
    return working


def finalize_flex_child_extents(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
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
        parent_node=parent_node,
    )


def bind_row_cross_axis_height(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_row: CleanDesignTreeNode | None = None,
) -> str:
    """Pin ROW cross-axis extent; infinite height crashes in scroll/flex hosts."""
    from figma_flutter_agent.generator.layout.common import (
        is_centered_glyph_badge,
        is_short_centered_glyph_text,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import row_is_status_pill_badge
    from figma_flutter_agent.generator.layout.flex_policy.stack import stack_is_card_metadata_host
    from figma_flutter_agent.generator.layout.flex_policy.text import text_in_card_metadata_rail
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_spaced_stack_skip_row_height_pin,
        _column_spaced_stack_needs_loose_overflow,
        _column_uses_loose_row_cross_axis_pin,
    )
    from figma_flutter_agent.generator.layout.flex_policy.alignment import flex_host_prefers_min_height_pin

    if is_centered_glyph_badge(node):
        return widget
    if is_short_centered_glyph_text(node):
        return widget
    if parent_row is not None and is_centered_glyph_badge(parent_row):
        return widget
    if parent_row is not None and row_is_status_pill_badge(parent_row):
        return widget
    if stack_is_card_metadata_host(node, parent_node=parent_row):
        return _bind_card_metadata_rail_width_only(node, widget)
    if (
        parent_row is not None
        and node.type == NodeType.TEXT
        and text_in_card_metadata_rail(
            node,
            parent_row,
            parent_type=NodeType.ROW,
        )
    ):
        return _bind_card_metadata_rail_width_only(node, widget)
    if _column_spaced_stack_skip_row_height_pin(node, parent_row=parent_row):
        return widget
    height = node.sizing.height
    if height is None or height <= 0:
        return widget
    height_lit = format_geometry_literal(height)
    if _row_cross_axis_pin_already_applied(widget, height_lit):
        return widget
    if "height: double.infinity" in widget:
        return _replace_infinite_height_literal(widget, height_lit)
    if flex_host_prefers_min_height_pin(node):
        if _column_uses_loose_row_cross_axis_pin(node, parent_row=parent_row):
            if _column_spaced_stack_needs_loose_overflow(node):
                return hoist_flex_parent_data(
                    lambda inner: (
                        f"ConstrainedBox("
                        f"constraints: BoxConstraints(minHeight: {height_lit}), "
                        f"child: {inner})"
                    ),
                    widget,
                )
            if _row_loose_cross_axis_pin_already_applied(widget, height_lit):
                return widget
            from figma_flutter_agent.generator.layout.common import (
                wrap_loose_vertical_overflow_child,
            )

            return hoist_flex_parent_data(
                lambda inner: wrap_loose_vertical_overflow_child(
                    inner,
                    max_height=height_lit,
                ),
                widget,
            )
        return hoist_flex_parent_data(
            lambda inner: (
                f"ConstrainedBox("
                f"constraints: BoxConstraints(minHeight: {height_lit}), "
                f"child: {inner})"
            ),
            widget,
        )
    if (
        parent_row is not None
        and parent_row.sizing.height_mode == SizingMode.HUG
        and node.type == NodeType.COLUMN
    ):
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


def _outer_sized_box_head_has_infinite_height(widget: str) -> bool:
    """Return True when the outermost ``SizedBox`` pins ``height: double.infinity``."""
    trimmed = widget.lstrip()
    if not trimmed.startswith("SizedBox("):
        return False
    head_end = trimmed.find(", child: ")
    if head_end < 0:
        return False
    return "height: double.infinity" in trimmed[:head_end]


def _replace_infinite_height_literal(widget: str, height_lit: str) -> str:
    """Swap the outer ``SizedBox`` ``height: double.infinity`` for a finite height."""
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    if not _outer_sized_box_head_has_infinite_height(widget):
        return widget
    head_end = trimmed.find(", child: ")
    head = trimmed[:head_end]
    tail = trimmed[head_end:]
    patched_head = head.replace("height: double.infinity", f"height: {height_lit}", 1)
    return f"{prefix}{patched_head}{tail}"


def _row_loose_cross_axis_pin_already_applied(
    widget: str,
    height_lit: str | None = None,
) -> bool:
    """Return True when a loose ROW cross-axis ``OverflowBox`` wrap is already present."""
    working = widget
    while True:
        unwrapped = _unwrap_flex_parent_data_wrapper(working)
        if unwrapped is None:
            break
        _, working = unwrapped
    trimmed = working.lstrip()
    if trimmed.startswith(
        "Align(alignment: Alignment.topCenter, child: OverflowBox("
    ):
        return True
    if height_lit is not None and trimmed.startswith(f"SizedBox(height: {height_lit}, child: "):
        return "OverflowBox(alignment: Alignment.topCenter, maxHeight: {height_lit}" in trimmed
    return False


def _row_cross_axis_pin_already_applied(widget: str, height_lit: str) -> bool:
    """Return True when the direct ROW flex child already pins cross-axis height.

    Nested ``OverflowBox`` wrappers inside stack descendants (e.g. positioned date
    slots) must not satisfy this guard — only the outer flex-child wrapper chain.
    """
    working = widget
    while True:
        unwrapped = _unwrap_flex_parent_data_wrapper(working)
        if unwrapped is None:
            break
        _, working = unwrapped

    trimmed = working.lstrip()
    if trimmed.startswith("SizedBox("):
        child_marker = ", child: "
        marker_idx = trimmed.find(child_marker)
        if marker_idx > 0:
            head = trimmed[:marker_idx]
            if f"height: {height_lit}" in head:
                return True
    if trimmed.startswith("ConstrainedBox("):
        head = trimmed.split("child:", 1)[0]
        if f"minHeight: {height_lit}" in head:
            return True
    if trimmed.startswith("Align(alignment: Alignment.topCenter, child: OverflowBox("):
        head = trimmed.split("child:", 1)[0]
        if f"maxHeight: {height_lit}" in head:
            return True
    return False


def _pin_row_cross_axis_height_inner(inner: str, height_lit: str) -> str:
    """Add a finite cross-axis height inside a ROW flex child expression."""
    trimmed = inner.lstrip()
    prefix = inner[: len(inner) - len(trimmed)]
    if trimmed.startswith("SizedBox("):
        child_marker = ", child: "
        marker_idx = trimmed.find(child_marker)
        if marker_idx > 0:
            head = trimmed[:marker_idx]
            tail = trimmed[marker_idx + len(child_marker):]
            if ", height:" in head:
                return inner
            if "width:" in head:
                return f"{prefix}{head}, height: {height_lit}, child: {tail}"
    return f"{prefix}SizedBox(height: {height_lit}, child: {inner})"


def _bind_card_metadata_rail_width_only(
    node: CleanDesignTreeNode,
    widget: str,
) -> str:
    """Pin metadata rail width without Figma glyph height (avoids ``FittedBox`` shrink)."""
    width = node.sizing.width
    if width is None or width <= 0:
        return widget
    width_lit = format_geometry_literal(width)
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    inner = widget
    if trimmed.startswith("SizedBox("):
        child_marker = ", child: "
        marker_idx = trimmed.find(child_marker)
        if marker_idx > 0:
            head = trimmed[:marker_idx]
            tail = trimmed[marker_idx + len(child_marker):]
            if ", height:" in head:
                head = re.sub(
                    r",\s*height:\s*[^,()]+",
                    "",
                    head,
                    count=1,
                )
            if "width:" in head:
                return f"{prefix}{head}, child: {tail}"
            inner = tail[:-1] if tail.endswith(")") else tail
    return f"{prefix}SizedBox(width: {width_lit}, child: {inner})"
