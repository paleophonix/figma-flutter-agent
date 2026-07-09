"""Flex wrap resolution and child extent management."""

from __future__ import annotations

import re
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
    return WrapKind.CONSTRAINED_BOX in slot.wraps or WrapKind.CROSS_STRETCH_WIDTH in slot.wraps


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
        _row_usable_main_span,
        _should_expand_sole_undersized_row_child,
        layout_fact_row_icon_stepper_control_row,
        layout_fact_row_numeric_counter_badge,
        layout_fact_row_product_card_price_footer_row,
        layout_fact_row_space_between_text_metric_row,
        layout_fact_row_status_pill_badge,
        layout_fact_row_tight_horizontal_pill_label,
        layout_fact_row_tight_overflow_guard_label_row,
        layout_fact_row_toolbar_leading_title_row,
        row_hosts_chip_beside_heading,
        row_hosts_equal_metric_cards,
    )
    from figma_flutter_agent.generator.layout.flex_policy.text import text_in_card_metadata_rail
    from figma_flutter_agent.parser.interaction import layout_fact_stack_compact_quantity_stepper

    if parent_type is None:
        return FlexWrapKind.NONE

    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_child_is_product_tile_metadata_slot,
    )

    if card_child_is_product_tile_metadata_slot(node, parent_node):
        return FlexWrapKind.NONE

    width_mode = node.sizing.width_mode
    height_mode = node.sizing.height_mode
    _column_peer_in_bounded_row(node, parent_node=parent_node)

    if parent_type == NodeType.ROW:
        from figma_flutter_agent.generator.layout.common import (
            is_short_centered_glyph_text,
            layout_fact_centered_glyph_badge,
        )
        from figma_flutter_agent.parser.interaction import (
            _subtree_has_currency_price,
            layout_fact_hosts_compact_checkbox_control,
        )

        if parent_node is not None and layout_fact_row_product_card_price_footer_row(parent_node):
            if column_hosts_product_card_stepper(
                node
            ) or layout_fact_stack_compact_quantity_stepper(node):
                return FlexWrapKind.NONE
            if node.type == NodeType.COLUMN and _subtree_has_currency_price(node):
                return FlexWrapKind.EXPANDED
        if parent_node is not None and layout_fact_row_space_between_text_metric_row(parent_node):
            return FlexWrapKind.NONE
        if layout_fact_hosts_compact_checkbox_control(node):
            return FlexWrapKind.NONE
        if layout_fact_row_toolbar_leading_title_row(node):
            return FlexWrapKind.NONE
        if layout_fact_centered_glyph_badge(node) or is_short_centered_glyph_text(node):
            return FlexWrapKind.NONE
        if parent_node is not None and layout_fact_centered_glyph_badge(parent_node):
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
            layout_fact_row_tight_horizontal_pill_label(node)
            or layout_fact_row_status_pill_badge(node)
            or layout_fact_row_numeric_counter_badge(node)
        ):
            return FlexWrapKind.NONE
        if parent_node is not None and _should_expand_sole_undersized_row_child(parent_node, node):
            return FlexWrapKind.EXPANDED
        if _row_child_keeps_intrinsic_width(node, parent_node):
            return FlexWrapKind.NONE
        if width_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if node.type == NodeType.ROW and _row_hosts_horizontal_flex_children(node):
            if (
                layout_fact_row_tight_horizontal_pill_label(node)
                or layout_fact_row_status_pill_badge(node)
                or layout_fact_row_numeric_counter_badge(node)
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
        if node.type == NodeType.COLUMN and _column_needs_expanded_under_row(
            node, parent_node=parent_node
        ):
            return FlexWrapKind.EXPANDED
        if width_mode in {SizingMode.FIXED, SizingMode.HUG} and node.type == NodeType.TEXT:
            if parent_node is not None and (
                layout_fact_row_tight_horizontal_pill_label(parent_node)
                or layout_fact_row_status_pill_badge(parent_node)
            ):
                return FlexWrapKind.NONE
            if parent_node is not None and layout_fact_row_tight_overflow_guard_label_row(
                parent_node
            ):
                return FlexWrapKind.EXPANDED
            if parent_node is not None and len(parent_node.children) > 1:
                parent_span = _row_usable_main_span(parent_node)
                if parent_span is not None and parent_span <= _INTRINSIC_ROW_CHILD_MAX_SPAN:
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
        if node.type == NodeType.ROW and layout_fact_row_icon_stepper_control_row(node):
            return FlexWrapKind.SIZED_BOX_WIDTH
        from figma_flutter_agent.generator.layout.flex_policy.row import (
            layout_fact_row_short_labeled_action,
        )

        if node.type == NodeType.ROW and layout_fact_row_short_labeled_action(node):
            return FlexWrapKind.NONE
        if height_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if width_mode == SizingMode.FILL:
            if node.type == NodeType.TEXT and ((node.style.text_align or "").upper() == "CENTER"):
                return FlexWrapKind.NONE
            return FlexWrapKind.SIZED_BOX_WIDTH
        from figma_flutter_agent.generator.layout.flex_policy.row import (
            _column_child_keeps_intrinsic_width,
        )

        if _column_child_keeps_intrinsic_width(node, parent_node):
            return FlexWrapKind.NONE

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


def strip_outer_infinite_width_sized_box(widget: str) -> str:
    """Remove an outer ``SizedBox(width: double.infinity)`` wrapper for row siblings."""
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    if not trimmed.startswith("SizedBox("):
        return widget
    child_marker = ", child: "
    marker_idx = trimmed.find(child_marker)
    if marker_idx < 0:
        return widget
    head = trimmed[:marker_idx]
    if "width: double.infinity" not in head:
        return widget
    child = _extract_balanced_prefix_child(trimmed, marker_idx + len(child_marker))
    if child is None:
        return widget
    height_field = ""
    if ", height:" in head:
        height_start = head.index(", height:")
        height_part = head[height_start + 2 :].strip()
        if height_part:
            height_field = f"{height_part}, "
    if height_field:
        return f"{prefix}SizedBox({height_field}child: {child})"
    return f"{prefix}{child}"


def bind_equal_row_flex_child(widget: str) -> str:
    """Wrap a horizontal row sibling with ``Expanded`` after stripping infinite width."""
    finite = strip_outer_infinite_width_sized_box(widget)
    unwrapped = _unwrap_flex_parent_data_wrapper(finite)
    if unwrapped is not None:
        marker, inner = unwrapped
        return f"{marker}{inner})"
    return f"Expanded(child: {finite})"


_FLEX_HOIST_WRAPPER_MARKERS = (
    "Align(",
    "Center(",
    "ClipRect(",
    "ConstrainedBox(",
    "Opacity(",
    "Padding(",
    "RepaintBoundary(",
    "SizedBox(",
)

_ILLEGAL_FLEX_PARENT_DATA_HOST_MARKERS = _FLEX_HOIST_WRAPPER_MARKERS


def collapse_nested_positioned_fill(widget: str) -> str:
    """Collapse ``Positioned(..., child: Positioned.fill(child: X))`` to a single ``Positioned``."""
    from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
        _find_matching_paren,
    )

    result = widget.strip()
    child_bridge = ", child: Positioned.fill("
    bridge_idx = result.find(child_bridge)
    if not result.startswith("Positioned(") or bridge_idx < 0:
        return widget
    fill_open = bridge_idx + len(child_bridge) - 1
    fill_close = _find_matching_paren(result, fill_open)
    if fill_close is None:
        return widget
    fill_inner = result[fill_open + 1 : fill_close]
    fill_child_idx = fill_inner.find("child: ")
    if fill_child_idx < 0:
        return widget
    fill_child = fill_inner[fill_child_idx + len("child: ") :].strip()
    if not fill_child:
        return widget
    outer_open = result.index("(")
    outer_close = _find_matching_paren(result, outer_open)
    if outer_close is None:
        return widget
    outer_inner = result[outer_open + 1 : outer_close]
    outer_child_idx = outer_inner.find("child: ")
    if outer_child_idx < 0:
        return widget
    prefix_fields = outer_inner[:outer_child_idx].rstrip().rstrip(",")
    if prefix_fields:
        return f"Positioned({prefix_fields}, child: {fill_child})"
    return f"Positioned(child: {fill_child})"


def repair_flex_parent_data_order(widget: str) -> str:
    """Hoist ``Expanded``/``Flexible`` above non-flex wrappers.

    Mis-ordered ``Wrapper(child: Expanded(...))`` breaks ROW/COLUMN parent data at
    runtime (e.g. ``Expanded`` under ``RepaintBoundary`` or ``SizedBox``).
    """
    widget = collapse_nested_positioned_fill(widget)
    descended = _repair_flex_parent_data_descend(widget)
    hoisted = _repair_flex_parent_data_once(descended)
    collapsed = _collapse_adjacent_flex_parent_data(hoisted)
    if collapsed != widget:
        return repair_flex_parent_data_order(collapsed)
    return widget


def _collapse_adjacent_flex_parent_data(widget: str) -> str:
    """Collapse nested ``Expanded``/``Flexible`` parent-data wrappers to one layer."""
    flex = _unwrap_flex_parent_data_wrapper(widget)
    if flex is None:
        return widget
    marker, inner = flex
    inner_flex = _unwrap_flex_parent_data_wrapper(inner)
    if inner_flex is None:
        return widget
    _, innermost = inner_flex
    return f"{marker}{innermost})"


_FLEX_PARENT_DATA_START_RE = re.compile(r"\b(?:const\s+)?(?:Expanded|Flexible)\s*\(")


def _starts_with_flex_parent_data_wrapper(widget: str) -> bool:
    """Return True when ``widget`` begins with an ``Expanded``/``Flexible`` wrapper."""
    trimmed = widget.lstrip()
    if trimmed.startswith("const "):
        trimmed = trimmed[6:].lstrip()
    return _FLEX_PARENT_DATA_START_RE.match(trimmed) is not None


def collect_illegal_flex_parent_data_host_spans(
    segment: str,
    *,
    base_offset: int = 0,
) -> list[int]:
    """Collect offsets where a box host wraps ``Expanded``/``Flexible`` illegally."""
    from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
        _find_matching_paren,
    )

    violations: list[int] = []
    for box_marker in _ILLEGAL_FLEX_PARENT_DATA_HOST_MARKERS:
        pos = 0
        while pos < len(segment):
            idx = segment.find(box_marker, pos)
            if idx < 0:
                break
            expr_start = idx - 6 if idx >= 6 and segment[idx - 6 : idx] == "const " else idx
            open_paren = segment.find("(", expr_start)
            if open_paren < 0:
                pos = idx + 1
                continue
            end = _find_matching_paren(segment, open_paren)
            if end is None:
                pos = idx + 1
                continue
            expr = segment[expr_start : end + 1]
            trimmed = expr.lstrip()
            child_marker = "child: "
            child_start = trimmed.find(child_marker)
            if child_start < 0:
                pos = idx + 1
                continue
            child = _extract_balanced_prefix_child(trimmed, child_start + len(child_marker))
            if child is None:
                pos = idx + 1
                continue
            if _starts_with_flex_parent_data_wrapper(child):
                violations.append(base_offset + expr_start)
                child_offset = expr.find(child)
                if child_offset >= 0:
                    violations.extend(
                        collect_illegal_flex_parent_data_host_spans(
                            child,
                            base_offset=base_offset + expr_start + child_offset,
                        )
                    )
            pos = idx + 1
    return violations


def collect_nested_flex_parent_data_spans(
    segment: str,
    *,
    base_offset: int = 0,
) -> list[int]:
    """Collect start offsets of flex wrappers whose direct child is also flex.

    Walks into flex-wrapper bodies so nested ``Expanded``/``Flexible`` pairs buried
    under ``SizedBox``/``Stack``/``Row`` are detected (not only file-top wrappers).
    """
    from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
        _find_matching_paren,
    )

    violations: list[int] = []
    pos = 0
    while pos < len(segment):
        match = _FLEX_PARENT_DATA_START_RE.search(segment, pos)
        if match is None:
            break
        start = match.start()
        expr_start = start - 6 if start >= 6 and segment[start - 6 : start] == "const " else start
        open_paren = segment.find("(", expr_start)
        if open_paren < 0:
            pos = start + 1
            continue
        end = _find_matching_paren(segment, open_paren)
        if end is None:
            pos = start + 1
            continue
        expr = segment[expr_start : end + 1]
        outer = _unwrap_flex_parent_data_wrapper(expr.strip())
        if outer is not None:
            _marker, inner = outer
            if _unwrap_flex_parent_data_wrapper(inner.strip()) is not None:
                violations.append(base_offset + expr_start)
            inner_offset = expr.find(inner)
            if inner_offset >= 0:
                violations.extend(
                    collect_nested_flex_parent_data_spans(
                        inner,
                        base_offset=base_offset + expr_start + inner_offset,
                    )
                )
        pos = start + 1
    return violations


def repair_nested_flex_parent_data_in_source(source: str) -> str:
    """Repair illegal flex parent-data wrappers anywhere in a Dart source."""
    from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
        _find_matching_paren,
    )

    updated = source
    while True:
        nested_spans = collect_nested_flex_parent_data_spans(updated)
        illegal_host_spans = collect_illegal_flex_parent_data_host_spans(updated)
        spans = sorted(set(nested_spans + illegal_host_spans))
        if not spans:
            return repair_overflowbox_unbounded_row_flex_in_source(updated)
        start = spans[0]
        open_paren = updated.find("(", start)
        if open_paren < 0:
            return repair_overflowbox_unbounded_row_flex_in_source(updated)
        end = _find_matching_paren(updated, open_paren)
        if end is None:
            return repair_overflowbox_unbounded_row_flex_in_source(updated)
        expr = updated[start : end + 1]
        repaired = repair_flex_parent_data_order(expr.strip())
        if repaired == expr.strip():
            return repair_overflowbox_unbounded_row_flex_in_source(updated)
        updated = updated[:start] + repaired + updated[end + 1 :]


_OVERFLOWBOX_MARKER = "OverflowBox("


def _extract_overflowbox_finite_max_width(expr: str) -> str | None:
    """Return a finite ``maxWidth`` literal from an ``OverflowBox`` expression."""
    marker = "maxWidth:"
    idx = expr.find(marker)
    if idx < 0:
        return None
    tail = expr[idx + len(marker) :].lstrip()
    end = 0
    depth = 0
    for index, char in enumerate(tail):
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                end = index
                break
            depth -= 1
        elif char == "," and depth == 0:
            end = index
            break
    else:
        end = len(tail)
    value = tail[:end].strip()
    if not value or value == "double.infinity":
        return None
    return value


def _pin_height_only_sizedbox_width_in_subtree(expr: str, width_lit: str) -> str:
    """Add ``width`` to height-only ``SizedBox`` hosts that wrap ``Expanded``."""
    marker = "SizedBox("
    updated = expr
    pos = 0
    changed = False
    while True:
        idx = updated.find(marker, pos)
        if idx < 0:
            break
        open_paren = updated.find("(", idx)
        from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
            _find_matching_paren,
        )

        end = _find_matching_paren(updated, open_paren)
        if end is None:
            break
        box = updated[idx : end + 1]
        child_marker = ", child: "
        child_idx = box.find(child_marker)
        if child_idx < 0:
            pos = end + 1
            continue
        head = box[:child_idx]
        if "height:" in head and "width:" not in head and "Expanded(" in box:
            new_box = f"{head}, width: {width_lit}{box[child_idx:]}"
            updated = updated[:idx] + new_box + updated[end + 1 :]
            changed = True
            pos = idx + len(new_box)
            continue
        pos = end + 1
    return updated if changed else expr


def repair_overflowbox_unbounded_row_flex_in_source(source: str) -> str:
    """Bound width for ``Expanded`` rows hosted under finite ``OverflowBox`` slots."""
    from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
        _find_matching_paren,
    )

    updated = source
    pos = 0
    while True:
        idx = updated.find(_OVERFLOWBOX_MARKER, pos)
        if idx < 0:
            return updated
        open_paren = updated.find("(", idx)
        end = _find_matching_paren(updated, open_paren)
        if end is None:
            return updated
        expr = updated[idx : end + 1]
        max_width = _extract_overflowbox_finite_max_width(expr)
        if max_width is not None and "Expanded(" in expr:
            repaired = _pin_height_only_sizedbox_width_in_subtree(expr, max_width)
            if repaired != expr:
                updated = updated[:idx] + repaired + updated[end + 1 :]
                pos = idx + len(repaired)
                continue
        pos = end + 1
    return repair_constrainedbox_unbounded_row_flex_in_source(updated)


_CONSTRAINEDBOX_MARKER = "ConstrainedBox("


def _find_enclosing_finite_sizedbox_width(source: str, before: int) -> str | None:
    """Return the nearest finite ``SizedBox(width: …)`` literal before *before*."""
    prefix = source[:before]
    marker = "SizedBox(width:"
    best: str | None = None
    pos = 0
    while True:
        idx = prefix.find(marker, pos)
        if idx < 0:
            return best
        tail = prefix[idx + len(marker) :].lstrip()
        if tail.startswith("double.infinity"):
            pos = idx + 1
            continue
        end = 0
        for index, char in enumerate(tail):
            if char in ",)":
                end = index
                break
        else:
            end = len(tail)
        value = tail[:end].strip()
        if value:
            best = value
        pos = idx + 1


def _constrainedbox_has_minheight_only_unbounded_width(expr: str) -> bool:
    """True when a ``ConstrainedBox`` only pins minHeight but hosts ``Expanded``."""
    bc_marker = "BoxConstraints("
    idx = expr.find(bc_marker)
    if idx < 0:
        return False
    open_paren = expr.find("(", idx)
    from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
        _find_matching_paren,
    )

    end = _find_matching_paren(expr, open_paren)
    if end is None:
        return False
    inner = expr[open_paren + 1 : end]
    if "minHeight:" not in inner:
        return False
    if "maxWidth:" in inner or "minWidth:" in inner:
        return False
    return "Expanded(" in expr


def _pin_width_on_minheight_constrainedbox(expr: str, width_lit: str) -> str:
    """Add finite width bounds to a minHeight-only ``ConstrainedBox``."""
    bc_marker = "constraints: BoxConstraints("
    idx = expr.find(bc_marker)
    if idx < 0:
        return expr
    insert_at = idx + len(bc_marker)
    return f"{expr[:insert_at]}minWidth: {width_lit}, maxWidth: {width_lit}, {expr[insert_at:]}"


def repair_constrainedbox_unbounded_row_flex_in_source(source: str) -> str:
    """Bound width for ``Expanded`` rows under minHeight-only ``ConstrainedBox`` hosts."""
    from figma_flutter_agent.generator.planned.reconcile.ast_helpers import (
        _find_matching_paren,
    )

    updated = source
    pos = 0
    while True:
        idx = updated.find(_CONSTRAINEDBOX_MARKER, pos)
        if idx < 0:
            return updated
        open_paren = updated.find("(", idx)
        end = _find_matching_paren(updated, open_paren)
        if end is None:
            return updated
        expr = updated[idx : end + 1]
        if not _constrainedbox_has_minheight_only_unbounded_width(expr):
            pos = end + 1
            continue
        width = _find_enclosing_finite_sizedbox_width(updated, idx)
        if width is None:
            pos = end + 1
            continue
        repaired = _pin_width_on_minheight_constrainedbox(expr, width)
        if repaired == expr:
            pos = end + 1
            continue
        updated = updated[:idx] + repaired + updated[end + 1 :]
        pos = idx + len(repaired)


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


def strip_flex_parent_data_for_scroll_item(widget: str) -> str:
    """Remove top-level ``Expanded``/``Flexible`` wrappers illegal in lazy scroll items."""
    stripped = widget
    while True:
        unwrapped = _unwrap_flex_parent_data_wrapper(stripped)
        if unwrapped is None:
            return stripped
        _, inner = unwrapped
        stripped = inner


_SCROLL_ITEM_BOX_MARKERS = (
    "SizedBox(",
    "Align(",
    "ConstrainedBox(",
    "RepaintBoundary(",
    "Padding(",
    "Center(",
    "Opacity(",
    "Semantics(",
)

_FLEX_CHILDREN_MARKERS = (
    "Stack(",
    "Row(",
    "Column(",
    "Wrap(",
)


def _split_top_level_children(source: str) -> list[str]:
    """Split a widget ``children`` list by top-level commas."""
    parts: list[str] = []
    depth_paren = 0
    depth_bracket = 0
    start = 0
    for index, char in enumerate(source):
        if char == "(":
            depth_paren += 1
        elif char == ")":
            depth_paren -= 1
        elif char == "[":
            depth_bracket += 1
        elif char == "]":
            depth_bracket -= 1
        elif char == "," and depth_paren == 0 and depth_bracket == 0:
            parts.append(source[start:index])
            start = index + 1
    parts.append(source[start:])
    return parts


def _strip_flex_in_children_array(widget: str) -> str | None:
    """Recurse into ``Stack``/``Row``/``Column`` ``children`` lists."""
    trimmed = widget.lstrip()
    prefix = widget[: len(widget) - len(trimmed)]
    for box_marker in _FLEX_CHILDREN_MARKERS:
        if not trimmed.startswith(box_marker):
            continue
        children_marker = "children: ["
        children_start = trimmed.find(children_marker)
        if children_start < 0:
            continue
        arr_start = children_start + len(children_marker)
        depth = 1
        arr_end = -1
        for index in range(arr_start, len(trimmed)):
            char = trimmed[index]
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    arr_end = index
                    break
        if arr_end < 0:
            continue
        children_src = trimmed[arr_start:arr_end]
        parts = _split_top_level_children(children_src)
        if not parts:
            continue
        repaired_parts = [strip_flex_parent_data_deep(part.strip()) for part in parts]
        if repaired_parts == [part.strip() for part in parts]:
            continue
        new_children = ", ".join(repaired_parts)
        head = trimmed[:arr_start]
        tail = trimmed[arr_end:]
        return f"{prefix}{head}{new_children}{tail}"
    return None


def strip_flex_parent_data_deep(widget: str) -> str:
    """Remove all ``Expanded``/``Flexible`` wrappers from a scroll item expression tree."""
    widget = strip_flex_parent_data_for_scroll_item(widget)
    markers = (
        "Expanded(child: ",
        "Flexible(fit: FlexFit.loose, flex: 0, child: ",
        "Flexible(fit: FlexFit.loose, child: ",
        "Flexible(child: ",
        "const Expanded(child: ",
        "const Flexible(fit: FlexFit.loose, flex: 0, child: ",
        "const Flexible(fit: FlexFit.loose, child: ",
        "const Flexible(child: ",
    )
    for _ in range(64):
        replaced = False
        for marker in markers:
            idx = widget.find(marker)
            if idx < 0:
                continue
            sub = widget[idx:]
            unwrapped = _unwrap_flex_parent_data_wrapper(sub)
            if unwrapped is None:
                continue
            open_marker, inner = unwrapped
            close_idx = idx + len(open_marker) + len(inner)
            if close_idx < len(widget) and widget[close_idx] == ")":
                widget = widget[:idx] + inner + widget[close_idx + 1 :]
                replaced = True
                break
        if not replaced:
            flex = _unwrap_flex_parent_data_wrapper(widget)
            if flex is not None:
                _, inner = flex
                widget = strip_flex_parent_data_deep(inner)
                replaced = True
            else:
                children_repaired = _strip_flex_in_children_array(widget)
                if children_repaired is not None:
                    widget = children_repaired
                    replaced = True
                else:
                    trimmed = widget.lstrip()
                    prefix = widget[: len(widget) - len(trimmed)]
                    for box_marker in _SCROLL_ITEM_BOX_MARKERS:
                        if not trimmed.startswith(box_marker):
                            continue
                        child_marker = "child: "
                        child_start = trimmed.find(child_marker)
                        if child_start < 0:
                            continue
                        child = _extract_balanced_prefix_child(
                            trimmed, child_start + len(child_marker)
                        )
                        if child is None:
                            continue
                        repaired_child = strip_flex_parent_data_deep(child)
                        if repaired_child == child:
                            continue
                        box_head = trimmed[: child_start + len(child_marker)]
                        widget = f"{prefix}{box_head}{repaired_child})"
                        replaced = True
                        break
        if not replaced:
            break
    return widget


def neutralize_parent_data_for_flex_child(widget: str) -> str:
    """Strip stack/flex parent-data wrappers before composing into Column/Row/Flex.

    Widgets finalized under a STACK parent may carry ``Positioned``; flex hosts require
    plain children. Likewise remove top-level ``Expanded``/``Flexible`` wrappers.
    """
    from figma_flutter_agent.generator.layout.widget_roots import (
        strip_stack_parent_data_wrappers,
    )

    return strip_flex_parent_data_for_scroll_item(strip_stack_parent_data_wrappers(widget))


def _unwrap_flex_parent_data_wrapper(widget: str) -> tuple[str, str] | None:
    """Return ``(wrapper_prefix, inner)`` for a top-level Expanded/Flexible wrapper."""
    trimmed = widget.lstrip()
    const_prefix = ""
    if trimmed.startswith("const "):
        const_prefix = "const "
        trimmed = trimmed[6:].lstrip()
    match = _FLEX_PARENT_DATA_START_RE.match(trimmed)
    if match is None:
        return None
    open_paren = trimmed.find("(", match.start())
    if open_paren < 0:
        return None
    child_marker = "child: "
    child_idx = trimmed.find(child_marker, open_paren)
    if child_idx < 0:
        return None
    inner = _extract_balanced_prefix_child(trimmed, child_idx + len(child_marker))
    if inner is None:
        return None
    marker = f"{const_prefix}{trimmed[: child_idx + len(child_marker)]}"
    return marker, inner


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
        from figma_flutter_agent.parser.interaction import (
            layout_fact_stack_product_recommendation_hero,
        )

        if not layout_fact_stack_product_recommendation_hero(
            node
        ) and not _planner_slot_handles_stack_bounds(node):
            bounded = _bound_stack_sized_box(node, widget, parent_type=parent_type)
            if bounded is not None:
                return bounded
    kind = resolve_flex_wrap(parent_type=parent_type, node=node, parent_node=parent_node)
    if kind == FlexWrapKind.NONE:
        from figma_flutter_agent.generator.layout.flex_policy.row import (
            _column_child_keeps_intrinsic_width,
        )

        if parent_type == NodeType.COLUMN and _column_child_keeps_intrinsic_width(
            node, parent_node
        ):
            return f"Align(alignment: Alignment.centerLeft, child: {widget})"
        return widget
    if kind == FlexWrapKind.EXPANDED:
        if _unwrap_flex_parent_data_wrapper(widget.lstrip()) is not None:
            return widget
        widget = _coerce_column_cross_stretch_for_row_expand(
            widget,
            parent_type=parent_type,
            node=node,
        )
        return f"Expanded(child: {widget})"
    if kind == FlexWrapKind.FLEXIBLE_LOOSE:
        if _unwrap_flex_parent_data_wrapper(widget.lstrip()) is not None:
            return widget
        return emit_flexible_loose(widget)
    if kind == FlexWrapKind.SIZED_BOX_WIDTH:
        if node.type == NodeType.STACK and _planner_slot_handles_stack_bounds(node):
            return widget
        return wrap_column_child_width_fill(
            widget,
            node,
            parent_node=parent_node,
            parent_type=parent_type,
        )
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
