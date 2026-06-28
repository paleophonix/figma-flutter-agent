"""Flex child extent pinning (pre/post wrap, ROW cross-axis height binding)."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.layout.flex_policy.wrap import (
    _unwrap_flex_parent_data_wrapper,
    hoist_flex_parent_data,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_ROW_TEXT_LINE_BOX_FRAME_RATIO = 0.85


def _row_padded_interior_height(row: CleanDesignTreeNode) -> float | None:
    """Return the vertical span inside a flex row after top/bottom padding."""
    frame_height = row.sizing.height
    if frame_height is None or float(frame_height) <= 0:
        return None
    padding = row.padding
    if padding is None:
        return float(frame_height)
    vertical = float(padding.top or 0.0) + float(padding.bottom or 0.0)
    interior = float(frame_height) - vertical
    return interior if interior > 0 else None


def _row_text_cross_axis_extent(node: CleanDesignTreeNode) -> float | None:
    """Prefer typographic line-box height when the Figma frame is shorter than strut metrics."""
    if node.type != NodeType.TEXT:
        return None
    frame_height = node.sizing.height
    font_size = node.style.font_size
    if font_size is None or font_size <= 0:
        return None
    line_box: float | None = None
    metrics = node.text_metrics_frame
    if metrics is not None and metrics.line_height_px and metrics.line_height_px > 0:
        line_box = float(metrics.line_height_px)
    else:
        ratio = node.style.line_height
        if ratio is not None and ratio > 0:
            line_box = float(font_size) * float(ratio)
    if line_box is None or line_box <= 0:
        return None
    if frame_height is None or frame_height <= 0:
        return line_box
    if float(frame_height) >= line_box * _ROW_TEXT_LINE_BOX_FRAME_RATIO:
        return float(frame_height)
    return line_box


def prepare_flex_child_extents(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Extent pins on inner content before ``Expanded``/``Flexible`` wrappers."""
    working = widget
    height = node.sizing.height
    if height is not None and height > 0 and _outer_sized_box_head_has_infinite_height(working):
        from figma_flutter_agent.generator.layout.widgets.positioned import (
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
    from figma_flutter_agent.generator.layout.flex_policy.buttons import (
        button_hosts_status_pill,
        horizontal_chip_button_should_hug_width,
    )
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_center_hug_child_wrap,
        column_child_should_center_hug,
        column_hosts_product_card_stepper,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_product_card_price_footer_row,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import _bound_stack_sized_box

    working = widget
    if (
        parent_type == NodeType.ROW
        and parent_node is not None
        and layout_fact_row_product_card_price_footer_row(parent_node)
        and column_hosts_product_card_stepper(node)
    ):
        from figma_flutter_agent.parser.interaction import stepper_stack_intrinsic_width

        slot_width = node.sizing.width
        intrinsic_width = stepper_stack_intrinsic_width(node)
        if slot_width is not None and float(slot_width) > 0:
            if intrinsic_width is not None and intrinsic_width > float(slot_width) + 1.0:
                working = (
                    "Align(alignment: Alignment.centerRight, child: FittedBox("
                    "fit: BoxFit.scaleDown, "
                    "alignment: Alignment.centerRight, "
                    f"child: {working}))"
                )
            else:
                width_lit = format_geometry_literal(float(slot_width))
                working = f"SizedBox(width: {width_lit}, child: {working})"
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
        layout_fact_column_compact_nav_tab,
    )

    if layout_fact_column_compact_nav_tab(node):
        working = (
            "ClipRect("
            "child: Align(alignment: Alignment.center, "
            f"child: {working}))"
        )
    if parent_type == NodeType.ROW:
        working = bind_row_cross_axis_height(
            node,
            working,
            parent_row=parent_node,
        )
        from figma_flutter_agent.parser.interaction import row_hosts_checkbox_label_pair

        if row_hosts_checkbox_label_pair(node) and not working.lstrip().startswith(
            "IntrinsicWidth("
        ):
            working = f"IntrinsicWidth(child: {working})"
    from figma_flutter_agent.generator.layout.flex_policy.wrap import repair_flex_parent_data_order

    return repair_flex_parent_data_order(working)


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
        is_short_centered_glyph_text,
        layout_fact_centered_glyph_badge,
    )
    from figma_flutter_agent.generator.layout.flex_policy.alignment import (
        flex_host_prefers_min_height_pin,
    )
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_spaced_stack_needs_loose_overflow,
        _column_spaced_stack_skip_row_height_pin,
        _column_uses_loose_row_cross_axis_pin,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_status_pill_badge,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_stack_card_metadata_host,
    )
    from figma_flutter_agent.generator.layout.flex_policy.text import text_in_card_metadata_rail

    if layout_fact_centered_glyph_badge(node):
        return widget
    if is_short_centered_glyph_text(node):
        return widget
    if parent_row is not None and layout_fact_centered_glyph_badge(parent_row):
        return widget
    if parent_row is not None and layout_fact_row_status_pill_badge(parent_row):
        return widget
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_compact_radio_label_row,
        layout_fact_payment_option_shell_column,
    )

    if parent_row is not None and layout_fact_compact_radio_label_row(parent_row):
        if node.type == NodeType.TEXT:
            return widget
    if layout_fact_payment_option_shell_column(node):
        return widget
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_should_emit_as_metadata_column,
    )

    if layout_fact_stack_card_metadata_host(node, parent_node=parent_row):
        if stack_should_emit_as_metadata_column(node, parent_node=parent_row):
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
        from figma_flutter_agent.generator.layout.flex_policy.column import (
            _column_uses_loose_row_cross_axis_pin,
        )

        if (
            parent_row is not None
            and _column_uses_loose_row_cross_axis_pin(node, parent_row=parent_row)
            and _column_spaced_stack_needs_loose_overflow(node)
        ):
            skip_height = node.sizing.height
            if skip_height is not None and skip_height > 0:
                skip_height_lit = format_geometry_literal(skip_height)
                if not _row_loose_cross_axis_pin_already_applied(widget, skip_height_lit):
                    from figma_flutter_agent.generator.layout.common import (
                        wrap_loose_vertical_overflow_child,
                    )

                    return hoist_flex_parent_data(
                        lambda inner: wrap_loose_vertical_overflow_child(
                            inner,
                            max_height=skip_height_lit,
                        ),
                        widget,
                    )
        return widget
    height = node.sizing.height
    if parent_row is not None and node.type == NodeType.TEXT:
        text_extent = _row_text_cross_axis_extent(node)
        if text_extent is not None:
            interior = _row_padded_interior_height(parent_row)
            if interior is not None and text_extent > interior + 0.5:
                return widget
            height = text_extent
    if height is None or height <= 0:
        return widget
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        positioned_slot_height_cap,
    )

    slot_cap = positioned_slot_height_cap(node)
    if slot_cap is not None:
        height = slot_cap
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
    if trimmed.startswith("Align(alignment: Alignment.topCenter, child: OverflowBox("):
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
            tail = trimmed[marker_idx + len(child_marker) :]
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
            tail = trimmed[marker_idx + len(child_marker) :]
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
