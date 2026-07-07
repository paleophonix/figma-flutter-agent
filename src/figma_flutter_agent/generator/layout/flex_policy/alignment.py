"""Axis alignment resolution for flex policy."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

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
    parent_type: NodeType | None = None,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Map Figma main-axis alignment to Flutter, with scroll-safe coercion."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_icon_stepper_control_row,
        layout_fact_row_product_card_price_footer_row,
    )

    if (
        node.type == NodeType.COLUMN
        and parent_type == NodeType.ROW
        and parent_node is not None
        and layout_fact_row_product_card_price_footer_row(parent_node)
        and parent_node.children
        and parent_node.children[0].id == node.id
    ):
        return "MainAxisAlignment.center"
    if node.type == NodeType.ROW and (
        layout_fact_row_icon_stepper_control_row(node)
        or layout_fact_row_product_card_price_footer_row(node)
    ):
        return "MainAxisAlignment.spaceBetween"
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
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Map Figma cross alignment to a Flutter value that is valid under ``parent_type``."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_needs_expanded_under_row,
        _column_subtree_needs_cross_stretch,
        _resolve_column_cross_axis,
        column_hosts_product_card_stepper,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        _resolve_row_cross_axis,
        layout_fact_row_product_card_price_footer_row,
    )

    if (
        node.type == NodeType.COLUMN
        and parent_type == NodeType.ROW
        and parent_node is not None
        and layout_fact_row_product_card_price_footer_row(parent_node)
        and column_hosts_product_card_stepper(node)
    ):
        return "CrossAxisAlignment.center"
    if (
        node.type == NodeType.COLUMN
        and parent_type == NodeType.ROW
        and (
            node.sizing.width_mode == SizingMode.FILL
            or _column_needs_expanded_under_row(node, parent_node=parent_node)
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
        return _resolve_row_cross_axis(node, parent_type=parent_type, default=cross_axis)
    if node.type == NodeType.COLUMN:
        return _resolve_column_cross_axis(node, parent_type=parent_type, default=cross_axis)
    return cross_axis


def emit_flexible_loose(widget: str, *, flex: int = 0) -> str:
    """Emit ``Flexible`` with explicit flex factor (default non-growing)."""
    if flex == 0:
        return f"Flexible(fit: FlexFit.loose, flex: 0, child: {widget})"
    return f"Flexible(fit: FlexFit.loose, child: {widget})"


def _flex_child_should_bind_fixed_height(node: CleanDesignTreeNode) -> bool:
    """Return True when a COLUMN width-fill child may also pin Figma frame height."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_is_text_primary,
        _is_form_field_group_column,
        layout_fact_column_product_card_footer_margin,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        _row_hosts_stack_flow_column_peer,
        _row_hosts_stacked_column_peer,
        layout_fact_row_status_pill_badge,
        layout_fact_row_tight_horizontal_pill_label,
    )
    from figma_flutter_agent.generator.layout.flex_policy.text import _text_has_multiple_lines

    height = node.sizing.height
    if height is None or height <= 0:
        return False
    if layout_fact_column_product_card_footer_margin(node):
        return False
    from figma_flutter_agent.parser.interaction.step import layout_fact_step_indicator_title_column

    if layout_fact_step_indicator_title_column(node):
        return False
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_payment_option_shell_column,
        layout_fact_payment_plan_trailing_price_cluster,
    )

    if layout_fact_payment_option_shell_column(node):
        return False
    if layout_fact_payment_plan_trailing_price_cluster(node):
        return False
    if flex_host_prefers_min_height_pin(node):
        return False
    if node.extracted_widget_ref:
        return False
    if node.type == NodeType.GRID and node.sizing.height_mode != SizingMode.FILL:
        return False
    if node.type == NodeType.STACK:
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            layout_fact_stack_positioned_subtitle_line,
        )
        from figma_flutter_agent.generator.layout.widgets.positioned import (
            _stack_has_bottom_anchored_child,
        )

        if _stack_has_bottom_anchored_child(node) or layout_fact_stack_positioned_subtitle_line(
            node
        ):
            return False
    if node.type == NodeType.COLUMN and _column_is_text_primary(node):
        return False
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        text_host_is_tight_positioned,
    )

    if node.type == NodeType.TEXT and text_host_is_tight_positioned(node):
        return False
    if node.type == NodeType.BUTTON:
        from figma_flutter_agent.parser.interaction import host_prefers_intrinsic_extent

        if host_prefers_intrinsic_extent(node):
            return False
    if node.sizing.height_mode == SizingMode.FILL:
        return True
    if node.type == NodeType.ROW and (
        _row_hosts_stacked_column_peer(node) or _row_hosts_stack_flow_column_peer(node)
    ):
        return False
    if layout_fact_row_status_pill_badge(node) or layout_fact_row_tight_horizontal_pill_label(node):
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
    if node.type == NodeType.INPUT:
        from figma_flutter_agent.parser.interaction import input_external_label_node

        if input_external_label_node(node) is not None:
            return False
    return True


def flex_host_prefers_min_height_pin(node: CleanDesignTreeNode) -> bool:
    """Return True when a host may grow past its Figma bbox under a ``Row``."""
    from figma_flutter_agent.generator.geometry.invariants.checks import (
        _predict_vertical_flow_extent,
    )
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        _column_prefers_min_height_pin,
        flex_host_hosts_intrinsic_flow_content,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        _row_hosts_stack_flow_column_peer,
        stack_should_flow_as_column,
    )

    if node.extracted_widget_ref:
        return True
    if _column_prefers_min_height_pin(node):
        return True
    if node.type == NodeType.STACK and stack_should_flow_as_column(node):
        return True
    if flex_host_hosts_intrinsic_flow_content(node):
        return True
    frame_height = node.sizing.height
    if frame_height is not None and frame_height > 0:
        predicted = _predict_vertical_flow_extent(node)
        if predicted is not None and predicted > float(frame_height) + 0.5:
            return True
    return _row_hosts_stack_flow_column_peer(node)
