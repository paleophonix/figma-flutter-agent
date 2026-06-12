"""Flex wrap resolution and child extent management."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode, WrapKind

_INTRINSIC_ROW_CHILD_MAX_SPAN = 120.0


class FlexWrapKind(StrEnum):
    """How to wrap a flex child before it is emitted or reconciled."""

    NONE = "none"
    EXPANDED = "expanded"
    FLEXIBLE_LOOSE = "flexible_loose"
    SIZED_BOX_WIDTH = "sized_box_width"


def _planner_slot_handles_stack_bounds(node: CleanDesignTreeNode) -> bool:
    """True when ``layout_slot`` wraps already bound stack extent for flex parents."""
    slot = node.layout_slot
    if slot is None:
        return False
    return (
        WrapKind.CONSTRAINED_BOX in slot.wraps
        or WrapKind.CROSS_STRETCH_WIDTH in slot.wraps
    )


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
    from figma_flutter_agent.generator.layout.flex_policy.buttons import button_hosts_status_pill
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_needs_expanded_under_row,
        column_hosts_product_card_stepper,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        _child_main_span,
        _column_peer_in_bounded_row,
        _row_child_keeps_intrinsic_width,
        _row_hosts_horizontal_flex_children,
        _row_title_column_should_expand_beside_chip,
        _row_usable_main_span,
        _should_expand_sole_undersized_row_child,
        row_hosts_chip_beside_heading,
        row_hosts_equal_metric_cards,
        row_is_icon_stepper_control_row,
        row_is_numeric_counter_badge,
        row_is_product_card_price_footer_row,
        row_is_space_between_text_metric_row,
        row_is_status_pill_badge,
        row_is_tight_horizontal_pill_label,
        row_is_tight_overflow_guard_label_row,
        row_is_toolbar_leading_title_row,
    )
    from figma_flutter_agent.generator.layout.flex_policy.text import text_in_card_metadata_rail
    from figma_flutter_agent.parser.interaction import stack_is_compact_quantity_stepper

    if parent_type is None:
        return FlexWrapKind.NONE

    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_child_is_product_tile_metadata_slot,
    )

    if card_child_is_product_tile_metadata_slot(node, parent_node):
        return FlexWrapKind.NONE

    width_mode = node.sizing.width_mode
    height_mode = node.sizing.height_mode
    bounded_row_peer = _column_peer_in_bounded_row(node, parent_node=parent_node)

    if parent_type == NodeType.ROW:
        from figma_flutter_agent.generator.layout.common import (
            is_centered_glyph_badge,
            is_short_centered_glyph_text,
        )
        from figma_flutter_agent.parser.interaction import (
            _subtree_has_currency_price,
            hosts_compact_checkbox_control,
        )

        if parent_node is not None and row_is_product_card_price_footer_row(parent_node):
            if (
                column_hosts_product_card_stepper(node)
                or stack_is_compact_quantity_stepper(node)
            ):
                return FlexWrapKind.NONE
            if node.type == NodeType.COLUMN and _subtree_has_currency_price(node):
                return FlexWrapKind.EXPANDED
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
            _column_needs_expanded_under_row(node, parent_node=parent_node)
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
                and row_is_tight_overflow_guard_label_row(parent_node)
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


_FLEX_HOIST_WRAPPER_MARKERS = (
    "ConstrainedBox(",
    "SizedBox(",
    "RepaintBoundary(",
)


def repair_flex_parent_data_order(widget: str) -> str:
    """Hoist ``Expanded``/``Flexible`` above non-flex wrappers.

    Mis-ordered ``Wrapper(child: Expanded(...))`` breaks ROW/COLUMN parent data at
    runtime (e.g. ``Expanded`` under ``RepaintBoundary`` or ``SizedBox``).
    """
    descended = _repair_flex_parent_data_descend(widget)
    hoisted = _repair_flex_parent_data_once(descended)
    collapsed = _collapse_adjacent_flex_parent_data(hoisted)
    if collapsed != widget:
        return repair_flex_parent_data_order(collapsed)
    return widget


def _collapse_adjacent_flex_parent_data(widget: str) -> str:
    """Collapse ``Expanded(Expanded(...))`` chains left by nested hoisting."""
    flex = _unwrap_flex_parent_data_wrapper(widget)
    if flex is None:
        return widget
    marker, inner = flex
    inner_flex = _unwrap_flex_parent_data_wrapper(inner)
    if inner_flex is None:
        return widget
    inner_marker, innermost = inner_flex
    if "Expanded(" in marker and "Expanded(" in inner_marker:
        return f"{marker}{innermost})"
    return widget


def _repair_flex_parent_data_descend(widget: str) -> str:
    """Recurse into flex/box children before hoisting at the current level."""
    flex = _unwrap_flex_parent_data_wrapper(widget)
    if flex is not None:
        marker, inner = flex
        repaired_inner = repair_flex_parent_data_order(inner)
        if repaired_inner == inner:
            return widget
        return f"{marker}{repaired_inner})"

    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    for box_marker in _FLEX_HOIST_WRAPPER_MARKERS:
        if not trimmed.startswith(box_marker):
            continue
        child_marker = "child: "
        child_start = trimmed.find(child_marker)
        if child_start < 0:
            continue
        child = _extract_balanced_prefix_child(trimmed, child_start + len(child_marker))
        if child is None:
            continue
        repaired_child = repair_flex_parent_data_order(child)
        if repaired_child == child:
            return widget
        box_head = trimmed[: child_start + len(child_marker)]
        return f"{prefix}{box_head}{repaired_child})"
    return widget


def _repair_flex_parent_data_once(widget: str) -> str:
    """Single pass: hoist one flex parent-data wrapper above a blocking ancestor."""
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    for box_marker in _FLEX_HOIST_WRAPPER_MARKERS:
        if not trimmed.startswith(box_marker):
            continue
        child_marker = "child: "
        child_start = trimmed.find(child_marker)
        if child_start < 0:
            continue
        child = _extract_balanced_prefix_child(trimmed, child_start + len(child_marker))
        if child is None:
            continue
        flex = _unwrap_flex_parent_data_wrapper(child)
        if flex is None:
            continue
        flex_marker, flex_inner = flex
        box_head = trimmed[: child_start + len(child_marker)]
        boxed = f"{prefix}{box_head}{flex_inner})"
        return f"{flex_marker}{boxed})"
    return widget


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
    from figma_flutter_agent.generator.layout.flex_policy.alignment import emit_flexible_loose
    from figma_flutter_agent.generator.layout.flex_policy.buttons import _bound_compact_icon_button
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _coerce_column_cross_stretch_for_row_expand,
        wrap_column_child_width_fill,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import _bound_stack_sized_box

    compact_icon = _bound_compact_icon_button(node, widget)
    if compact_icon is not None:
        widget = compact_icon
    if parent_type in {NodeType.COLUMN, NodeType.CARD} and node.type == NodeType.STACK:
        from figma_flutter_agent.parser.interaction import stack_is_product_recommendation_hero

        if not stack_is_product_recommendation_hero(node) and not _planner_slot_handles_stack_bounds(
            node
        ):
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
        if node.type == NodeType.STACK and _planner_slot_handles_stack_bounds(node):
            return widget
        return wrap_column_child_width_fill(widget, node)
    return widget


from figma_flutter_agent.generator.layout.flex_policy.extents import (  # noqa: E402,F401
    _bind_card_metadata_rail_width_only,
    _outer_sized_box_head_has_infinite_height,
    _pin_row_cross_axis_height_inner,
    _replace_infinite_height_literal,
    _row_cross_axis_pin_already_applied,
    _row_loose_cross_axis_pin_already_applied,
    bind_row_cross_axis_height,
    finalize_flex_child_extents,
    post_flex_layout_slot_extents,
    prepare_flex_child_extents,
)
