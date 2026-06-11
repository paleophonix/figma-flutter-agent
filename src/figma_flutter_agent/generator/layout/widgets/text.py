"""Text layout emitters: multiline, button-label, stack-position wrappers."""

from __future__ import annotations

from figma_flutter_agent.generator.figma_anchor import figma_value_key_arg
from figma_flutter_agent.generator.layout.common import (
    escape_dart_string,
)
from figma_flutter_agent.generator.layout.style import (
    text_widget_trailing_params,
)
from figma_flutter_agent.parser.interaction import (
    _is_footer_link_text_node,
    _label_matches_action_hint,
    _local_nodes,
    _stack_spans_primary_button_and_footer_link,
    button_stack_has_left_icon,
    primary_surface_node,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
)
from figma_flutter_agent.parser.render_bounds import (
    child_has_outward_paint,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    StackPlacement,
)

from .layout import (
    _positioned_fields,
    _positioned_fields_from_pins,
    _should_omit_positioned_height,
)
from .position import (
    _child_needs_positioned_bounds,
    _ensure_positioned_stack_bounds,
)
from .shared import _node_layout_size
from .svg import (
    _effective_svg_dimensions,
    _is_skip_control_stack,
    _stroke_line_top_adjustment,
)


def _render_explicit_multiline_text_lines(
    node: CleanDesignTreeNode,
    *,
    style_expr: str,
    text_align_suffix: str,
) -> str | None:
    """Preserve Figma hard line breaks in one ``Text`` without ``maxLines: 1`` clipping."""
    if node.text_spans:
        return None
    raw = (node.text or "").strip()
    if "\n" not in raw:
        return None
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    from figma_flutter_agent.parser.interaction.forms import text_is_payment_option_secondary

    payment_subtitle = text_is_payment_option_secondary(node)
    trailing = text_widget_trailing_params(
        node.style,
        text_align_suffix=text_align_suffix,
        soft_wrap=False,
        omit_strut=payment_subtitle,
        optical_center=payment_subtitle,
    )
    text = escape_dart_string(raw)
    return f"Text('{text}', style: {style_expr}, {trailing})"


def _wrap_bounded_positioned_slot_child(
    widget: str,
    *,
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Clip slot overflow without ``RenderFlex`` layout assertions.

    ``ClipRect`` alone only affects painting. When a ``Column`` with
    ``mainAxisSize: min`` is fractionally taller than its ``Positioned`` slot
    (text metrics rounding, flex ``spacing``), Flutter still throws overflow.
    ``OverflowBox`` loosens the flex axis while the outer ``Positioned`` slot
    keeps the painted bounds stable.
    """
    from figma_flutter_agent.generator.layout.flex_policy import (
        column_bounded_slot_needs_vertical_scroll,
        column_bounded_slot_should_grow,
        stack_metadata_timestamp_host,
    )

    if stack_metadata_timestamp_host(node, parent_node=parent_node):
        return widget

    if column_bounded_slot_should_grow(node):
        return widget

    if column_bounded_slot_needs_vertical_scroll(node):
        scroll_body = f"SingleChildScrollView(child: {widget})"
        if child_has_outward_paint(node):
            return scroll_body
        return f"ClipRect(child: {scroll_body})"

    placement = node.stack_placement
    width, height = _node_layout_size(node, placement)
    # ``widget`` already includes this node's ``Padding`` (applied in ``_finalize_widget``
    # before ``_apply_stack_position``). ``OverflowBox`` max extent must therefore match
    # the full positioned slot — subtracting padding here double-counts and starves flex
    # children (e.g. 84px slot + 36px padding → 12px for ``Column`` → RenderFlex overflow).
    if node.type == NodeType.ROW:
        align = "Alignment.centerLeft"
        if width is not None and width > 0:
            loosen = f"maxWidth: {format_geometry_literal(width)}, "
        else:
            loosen = "maxWidth: double.infinity, "
    else:
        align = "Alignment.topCenter"
        if height is not None and height > 0:
            loosen = f"maxHeight: {format_geometry_literal(height)}, "
        else:
            loosen = "maxHeight: double.infinity, "
    inner = (
        f"Align(alignment: {align}, child: OverflowBox("
        f"alignment: {align}, {loosen}"
        f"child: {widget}))"
    )
    if child_has_outward_paint(node):
        return inner
    return f"ClipRect(child: {inner})"


def _apply_stack_position(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None = None,
    fill_parent: bool = False,
    scroll_content_root: bool = False,
) -> str:
    if scroll_content_root:
        return widget
    if parent_type not in {NodeType.STACK, NodeType.BUTTON}:
        return widget
    if (
        parent_node is not None
        and parent_node.type == NodeType.STACK
    ):
        from figma_flutter_agent.generator.layout.flex_policy import (
            stack_should_flow_as_centered_wrap,
            stack_should_flow_as_column,
        )

        if stack_should_flow_as_column(parent_node):
            return widget
        if stack_should_flow_as_centered_wrap(parent_node):
            return widget
    if fill_parent:
        return f"Positioned.fill(child: {widget})"
    placement = node.stack_placement
    if placement is None and node.layout_positioning == "ABSOLUTE":
        placement = StackPlacement(left=node.offset_x, top=node.offset_y)
    if placement is None:
        return widget
    if parent_node is not None and parent_node.type == NodeType.STACK:
        parent_width = parent_node.sizing.width
        if parent_width is None and parent_node.stack_placement is not None:
            parent_width = parent_node.stack_placement.width
        if parent_width is not None and parent_width > 0:
            from figma_flutter_agent.parser.layout import (
                clamp_stack_child_placement_to_parent,
            )

            placement = clamp_stack_child_placement_to_parent(
                placement,
                float(parent_width),
            )
    parent_height: float | None = None
    if parent_node is not None:
        parent_height = parent_node.sizing.height
        if parent_height is None and parent_node.stack_placement is not None:
            parent_height = parent_node.stack_placement.height
    slot = node.layout_slot
    if slot is not None and slot.positioned_pins is not None:
        fields = _positioned_fields_from_pins(
            slot.positioned_pins,
            render_boundary=node.render_boundary,
            parent_height=parent_height,
        )
    else:
        fields = _positioned_fields(
            placement,
            render_boundary=node.render_boundary,
            parent_height=parent_height,
        )
    if _child_needs_positioned_bounds(node, widget):
        _ensure_positioned_stack_bounds(
            fields, node, placement, parent_height=parent_height
        )
    if _should_omit_positioned_height(node, parent_node=parent_node):
        fields[:] = [field for field in fields if not field.startswith("height:")]
    from figma_flutter_agent.generator.layout.responsive import (
        should_stretch_bottom_positioned_horizontal,
        stretch_positioned_fields_horizontal,
    )

    if placement is not None and should_stretch_bottom_positioned_horizontal(placement):
        stretch_positioned_fields_horizontal(fields)
    width, height = _node_layout_size(node, placement)
    _raw_width, effective_height = _effective_svg_dimensions(node, width, height)
    adjusted_top = _stroke_line_top_adjustment(node, placement, effective_height)
    if (
        adjusted_top is not None
        and placement.top is not None
        and adjusted_top != placement.top
    ):
        fields = [
            field if not field.startswith("top:") else f"top: {adjusted_top}"
            for field in fields
        ]
    fields_str = ", ".join(fields)
    child = widget
    slot_height = placement.height
    if (
        slot_height is not None
        and slot_height > 0
        and node.type in {NodeType.COLUMN, NodeType.ROW, NodeType.CONTAINER}
    ):
        child = _wrap_bounded_positioned_slot_child(
            child,
            node=node,
            parent_node=parent_node,
        )
    return f"Positioned({fields_str}, {figma_value_key_arg(node.id)}, child: {child})"


def _should_center_text_in_button_stack(
    parent_node: CleanDesignTreeNode | None,
    text_node: CleanDesignTreeNode,
) -> bool:
    from figma_flutter_agent.parser.interaction import _is_footer_link_text_node

    if parent_node is None or text_node.type != NodeType.TEXT:
        return False
    if _is_footer_link_text_node(text_node):
        return False
    font_size = text_node.style.font_size if text_node.style else None
    if font_size is not None and float(font_size) >= 22.0:
        return False
    if _is_skip_control_stack(parent_node):
        return False
    if parent_node.type == NodeType.BUTTON:
        from figma_flutter_agent.parser.interaction import (
            button_has_list_tile_row_body,
            button_is_left_aligned_text_label,
            button_stack_has_left_icon,
        )

        if button_has_list_tile_row_body(parent_node):
            return False
        if button_stack_has_left_icon(parent_node):
            return False
        if button_is_left_aligned_text_label(parent_node):
            return False
        return True
    if parent_node.type != NodeType.STACK:
        return False
    if stack_interaction_kind(parent_node) == "button":
        return True
    text_nodes = [
        item
        for item in _local_nodes(parent_node, 2)
        if item.type == NodeType.TEXT and item.text
    ]
    return _stack_spans_primary_button_and_footer_link(
        parent_node, text_nodes=text_nodes
    )


def _button_label_should_center_in_parent(
    parent_node: CleanDesignTreeNode,
    *,
    placement: StackPlacement,
    text_node: CleanDesignTreeNode,
) -> bool:
    """Center CTA copy in the full button when an icon sits left or the label is wide."""
    if button_stack_has_left_icon(parent_node):
        return True
    parent_width = parent_node.sizing.width
    text_width = (
        placement.width if placement.width is not None else text_node.sizing.width
    )
    if parent_width is None or text_width is None or parent_width <= 0:
        return False
    return float(text_width) >= float(parent_width) * 0.55


def _ensure_text_center_align(widget: str) -> str:
    """Add ``textAlign: TextAlign.center`` when the label is centered in a button row."""
    if "textAlign:" in widget:
        return widget
    if "Text(" in widget and "textScaler:" in widget:
        return widget.replace(
            "textScaler:", "textAlign: TextAlign.center, textScaler:", 1
        )
    return widget


def _position_button_stack_label(
    widget: str,
    *,
    text_node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> str:
    """Vertically center CTA labels inside absolute button stacks."""
    parent_height = parent_node.sizing.height
    parent_width = parent_node.sizing.width
    text_nodes = [
        item
        for item in _local_nodes(parent_node, 2)
        if item.type == NodeType.TEXT and item.text
    ]
    if _stack_spans_primary_button_and_footer_link(parent_node, text_nodes=text_nodes):
        surface = primary_surface_node(parent_node)
        if surface is not None:
            if surface.sizing.height is not None and surface.sizing.height > 0:
                parent_height = surface.sizing.height
            if surface.sizing.width is not None and surface.sizing.width > 0:
                parent_width = surface.sizing.width
    if parent_height is None or parent_height <= 0:
        return _apply_stack_position(
            text_node,
            widget,
            parent_type=NodeType.STACK,
            fill_parent=False,
        )
    center_in_parent = _button_label_should_center_in_parent(
        parent_node,
        placement=placement,
        text_node=text_node,
    )
    if not center_in_parent:
        action_labels = [
            item
            for item in text_nodes
            if _label_matches_action_hint(
                (item.text or item.name or "").strip().lower()
            )
            and not _is_footer_link_text_node(item)
        ]
        if (
            stack_interaction_kind(parent_node) == "button"
            and len(text_nodes) == 1
            and len(action_labels) == 1
        ):
            center_in_parent = True
        else:
            center_in_parent = _stack_spans_primary_button_and_footer_link(
                parent_node,
                text_nodes=text_nodes,
            )
    if center_in_parent and parent_width is not None and parent_width > 0:
        fields = [
            "left: 0.0",
            f"width: {format_geometry_literal(parent_width)}",
            "top: 0.0",
            f"height: {format_geometry_literal(parent_height)}",
        ]
        label_widget = _ensure_text_center_align(widget)
        centered = f"Align(alignment: Alignment.center, child: {label_widget})"
    else:
        left = placement.left if placement.left is not None else 0.0
        width = (
            placement.width if placement.width is not None else text_node.sizing.width
        )
        fields = [
            f"left: {format_geometry_literal(left)}",
            "top: 0.0",
            f"height: {format_geometry_literal(parent_height)}",
        ]
        if width is not None and width > 0:
            fields.insert(1, f"width: {format_geometry_literal(width)}")
        centered = f"Align(alignment: Alignment.centerLeft, child: {widget})"
    return f"Positioned({', '.join(fields)}, {figma_value_key_arg(text_node.id)}, child: {centered})"


