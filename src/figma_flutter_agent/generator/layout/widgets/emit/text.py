"""TEXT node rendering branch."""

from __future__ import annotations

from figma_flutter_agent.generator.emit_text_span import (
    emit_text_rich,
    emit_text_span_children_from_node,
)
from figma_flutter_agent.generator.layout.common import (
    escape_figma_text_literal,
    is_short_centered_glyph_text,
    layout_fact_centered_glyph_badge,
    node_with_display_accessibility,
)
from figma_flutter_agent.generator.layout.style import (
    should_emit_strut_style,
    strut_style_expr,
    text_align_expr,
    text_style_expr,
    text_widget_trailing_params,
    wrap_painted_pill_scale_down_label,
    wrap_tight_chip_label,
)
from figma_flutter_agent.parser.interaction import (
    is_link_text,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

from ..button import _wrap_link_text
from ..finalize import _finalize_widget, _wrap_accessibility
from ..layout import _positioned_fields, positioned_fields_for_stack_center_fill
from ..position import _ensure_positioned_stack_bounds
from ..svg import (
    _clamp_centered_text_to_parent_stack,
    _is_skip_control_stack,
    _should_center_in_parent_stack,
    _skip_control_numeral_top,
    _wrap_centered_stack_child,
)
from ..text import (
    _position_button_stack_label,
    _render_explicit_multiline_text_lines,
    _should_center_text_in_button_stack,
)


def render_text_node(
    node: CleanDesignTreeNode,
    ctx: dict,
    flow: dict,
    *,
    recurse,
) -> str:
    """Render a NodeType.TEXT node."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    bundled_font_families = ctx["bundled_font_families"]
    dart_weight_overrides_by_family = ctx["dart_weight_overrides_by_family"]
    text_theme_slot_by_style_name = ctx["text_theme_slot_by_style_name"]
    text_theme_size_slots = ctx["text_theme_size_slots"]
    ctx["de_archetype_pass"]

    from figma_flutter_agent.generator.layout.flex_policy import (
        layout_fact_row_status_pill_badge,
        layout_fact_stack_numeric_glyph_overlay_host,
        text_host_is_tight_positioned,
        text_in_card_metadata_rail,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_numeric_counter_badge,
    )
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_column_compact_nav_tab,
        layout_fact_stack_bottom_nav_tab_glyph_column,
    )
    from figma_flutter_agent.parser.interaction import layout_fact_stack_category_component_tile
    from figma_flutter_agent.parser.interaction.icons import (
        layout_fact_stack_vertical_icon_label_chip_tile,
    )

    align = text_align_expr(node.style)
    align_suffix = f", textAlign: {align}" if align else ""
    metadata_rail = text_in_card_metadata_rail(
        node,
        parent_node,
        parent_type=parent_type,
    )
    nav_tab_column_parent = (
        parent_node is not None
        and (
            layout_fact_column_compact_nav_tab(parent_node)
            or layout_fact_stack_bottom_nav_tab_glyph_column(parent_node)
        )
    )
    bounded_single_line_label_slot = nav_tab_column_parent

    centered_glyph_parent = parent_node is not None and layout_fact_centered_glyph_badge(parent_node)
    from figma_flutter_agent.generator.layout.flex_policy import (
        button_is_pill_with_centered_label,
    )
    from figma_flutter_agent.parser.interaction.forms import (
        text_is_payment_option_secondary,
    )

    payment_subtitle = text_is_payment_option_secondary(node)
    notification_counter_glyph = (
        parent_node is not None
        and parent_type == NodeType.STACK
        and layout_fact_stack_numeric_glyph_overlay_host(parent_node)
        and (node.text or "").strip().isdigit()
        and len((node.text or "").strip()) <= 3
    )
    omit_glyph_strut = (
        centered_glyph_parent
        or is_short_centered_glyph_text(node)
        or payment_subtitle
        or notification_counter_glyph
        or (
            parent_node is not None
            and parent_type in {NodeType.ROW, NodeType.COLUMN}
            and layout_fact_row_numeric_counter_badge(parent_node)
        )
        or (text_host_is_tight_positioned(node) and not should_emit_strut_style(node.style))
        or (
            parent_node is not None
            and parent_type in {NodeType.ROW, NodeType.COLUMN}
            and layout_fact_row_status_pill_badge(parent_node)
        )
        or (
            parent_node is not None
            and parent_type == NodeType.BUTTON
            and button_is_pill_with_centered_label(parent_node)
        )
    )
    strut = None if omit_glyph_strut else strut_style_expr(
        node.style,
        omit_leading=metadata_rail,
        node=node,
    )
    explicit_multiline = False
    if node.text_spans:
        span_parts = emit_text_span_children_from_node(
            node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        widget = emit_text_rich(
            span_parts,
            text_align_suffix=align_suffix,
            strut_style=strut,
        )
    else:
        text = escape_figma_text_literal(node)
        style_expr = text_style_expr(
            node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
            omit_line_height_for_strut=strut is not None,
            omit_line_height=omit_glyph_strut,
        )
        column_widget = _render_explicit_multiline_text_lines(
            node,
            style_expr=style_expr,
            text_align_suffix=align_suffix,
        )
        explicit_multiline = column_widget is not None
        if explicit_multiline:
            widget = column_widget
        else:
            from figma_flutter_agent.generator.layout.flex_policy.row import (
                layout_fact_row_tight_horizontal_pill_label,
                layout_fact_row_tight_overflow_guard_label_row,
            )

            text = escape_figma_text_literal(node)
            pill_label = (
                parent_node is not None
                and parent_type == NodeType.ROW
                and layout_fact_row_tight_horizontal_pill_label(parent_node)
            )
            from figma_flutter_agent.parser.interaction.chip_variant import (
                is_tag_component_chip_row,
            )

            if pill_label and parent_node is not None and is_tag_component_chip_row(parent_node):
                pill_label = False
            painted_pill_label = (
                pill_label
                and parent_node is not None
                and bool(parent_node.style.background_color)
            )
            guard_label_row = (
                parent_node is not None
                and parent_type == NodeType.ROW
                and layout_fact_row_tight_overflow_guard_label_row(parent_node)
            )
            from figma_flutter_agent.parser.interaction.step import (
                layout_fact_step_indicator_title_column,
            )

            step_title_label = (
                parent_node is not None
                and layout_fact_step_indicator_title_column(parent_node)
            )
            single_line_clipped_label = (
                guard_label_row
                or metadata_rail
                or bounded_single_line_label_slot
                or step_title_label
                or (
                    parent_node is not None
                    and layout_fact_stack_vertical_icon_label_chip_tile(parent_node)
                )
            )
            if payment_subtitle and "\n" not in (node.text or ""):
                trailing = text_widget_trailing_params(
                    node.style,
                    text_align_suffix=align_suffix,
                    omit_strut=True,
                    optical_center=True,
                    soft_wrap=False,
                    clip_single_line=True,
                )
            elif step_title_label:
                trailing = text_widget_trailing_params(
                    node.style,
                    text_align_suffix=", textAlign: TextAlign.center",
                    omit_strut=True,
                    soft_wrap=False,
                    clip_single_line=True,
                )
            elif guard_label_row:
                trailing = text_widget_trailing_params(
                    node.style,
                    text_align_suffix=align_suffix,
                    clip_single_line=True,
                )
            elif single_line_clipped_label:
                trailing = text_widget_trailing_params(
                    node.style,
                    text_align_suffix=align_suffix,
                    omit_strut=omit_glyph_strut,
                    soft_wrap=False,
                    clip_single_line=True,
                )
            elif notification_counter_glyph:
                trailing = text_widget_trailing_params(
                    node.style,
                    text_align_suffix=", textAlign: TextAlign.center",
                    omit_strut=True,
                    optical_center=True,
                    soft_wrap=False,
                    clip_single_line=True,
                )
            else:
                from figma_flutter_agent.generator.layout.flex_policy.text import (
                    geometry_multiline_max_lines,
                    text_is_geometry_multiline,
                )

                geometry_multiline = text_is_geometry_multiline(node)
                trailing = text_widget_trailing_params(
                    node.style,
                    text_align_suffix=align_suffix,
                    omit_strut=omit_glyph_strut,
                    optical_center=omit_glyph_strut
                    and (node.style.text_align or "").upper() == "CENTER",
                    soft_wrap=True if geometry_multiline else None,
                )
                if geometry_multiline:
                    trailing = f"{trailing}, maxLines: {geometry_multiline_max_lines(node)}"
            widget = f"Text('{text}', style: {style_expr}, {trailing})"
            if notification_counter_glyph:
                widget = f"Center(child: {widget})"
            if painted_pill_label:
                widget = wrap_painted_pill_scale_down_label(widget)
            elif pill_label and not painted_pill_label:
                widget = wrap_tight_chip_label(widget)
            elif (
                metadata_rail
                and not notification_counter_glyph
                and not nav_tab_column_parent
                and not (parent_node is not None and layout_fact_stack_category_component_tile(parent_node))
                and not (
                    parent_node is not None
                    and layout_fact_stack_vertical_icon_label_chip_tile(parent_node)
                )
            ):
                widget = wrap_tight_chip_label(
                    widget,
                    align="Alignment.centerRight",
                )
                if parent_type == NodeType.ROW:
                    text_width = node.sizing.width
                    if text_width is not None and text_width > 0:
                        widget = (
                            f"SizedBox(width: {format_geometry_literal(text_width)}, "
                            f"child: Align(alignment: Alignment.centerRight, child: {widget}))"
                        )
    if (
        node.style.text_align == "LEFT"
        and node.sizing.width_mode == SizingMode.FILL
        and parent_type in {NodeType.COLUMN, NodeType.ROW}
    ):
        widget = (
            "SizedBox(width: double.infinity, child: "
            f"Align(alignment: Alignment.centerLeft, child: {widget}))"
        )
    elif (node.style.text_align or "").upper() == "CENTER" and parent_type in {
        NodeType.COLUMN,
        NodeType.STACK,
    }:
        if nav_tab_column_parent and parent_node is not None:
            parent_width = parent_node.sizing.width
            if parent_width is not None and float(parent_width) > 0:
                width_lit = format_geometry_literal(float(parent_width))
                widget = f"SizedBox(width: {width_lit}, child: Center(child: {widget}))"
            else:
                widget = f"Center(child: {widget})"
        else:
            widget = f"SizedBox(width: double.infinity, child: Center(child: {widget}))"
    text_width = node.sizing.width
    if (
        "\n" in (node.text or "")
        and text_width is not None
        and text_width > 0
        and node.sizing.width_mode != SizingMode.FILL
        and (node.style.text_align or "").upper() != "CENTER"
    ):
        widget = f"SizedBox(width: {format_geometry_literal(text_width)}, child: {widget})"
    font_size = node.style.font_size
    text_height = node.sizing.height
    if (
        not explicit_multiline
        and "\n" not in (node.text or "")
        and text_width is not None
        and text_width > 0
        and text_height is not None
        and font_size is not None
        and float(text_height) > float(font_size) * 1.6
        and parent_type in {NodeType.COLUMN, NodeType.STACK}
        and node.sizing.width_mode != SizingMode.FILL
        and (node.style.text_align or "").upper() != "CENTER"
    ):
        widget = f"SizedBox(width: {format_geometry_literal(text_width)}, child: {widget})"
    from figma_flutter_agent.generator.layout.flex_policy.text import (
        text_preserves_intrinsic_wrap_width,
    )

    if text_preserves_intrinsic_wrap_width(node) and parent_type == NodeType.COLUMN:
        widget = f"Align(alignment: Alignment.centerLeft, child: {widget})"
    if is_link_text(node.text) and parent_type != NodeType.BUTTON:
        widget = _wrap_link_text(widget)
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_active_tab_pill,
    )

    if (
        parent_node is not None
        and parent_type in {NodeType.STACK, NodeType.BUTTON}
        and node.stack_placement is not None
        and (
            _should_center_text_in_button_stack(parent_node, node)
            or layout_fact_stack_vertical_icon_label_chip_tile(parent_node)
            or layout_fact_stack_bottom_nav_active_tab_pill(parent_node)
        )
    ):
        widget = _wrap_accessibility(node_with_display_accessibility(node), widget)
        if scroll_content_root:
            return widget
        return _position_button_stack_label(
            widget,
            text_node=node,
            parent_node=parent_node,
            placement=node.stack_placement,
        )
    from figma_flutter_agent.parser.interaction.step import (
        layout_fact_step_indicator_completed,
        layout_fact_step_indicator_glyph_stack,
    )

    if parent_node is not None and layout_fact_step_indicator_glyph_stack(parent_node):
        if layout_fact_step_indicator_completed(parent_node) and (node.text or "").strip().isdigit():
            return "const SizedBox.shrink()"
        if (node.text or "").strip().isdigit():
            style_expr = text_style_expr(
                node,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
            text = escape_figma_text_literal(node)
            trailing = text_widget_trailing_params(
                node.style,
                text_align_suffix=", textAlign: TextAlign.center",
            )
            widget = (
                f"Text('{text}', style: {style_expr}, {trailing})"
            )
            widget = _wrap_accessibility(
                node_with_display_accessibility(node),
                f"Center(child: {widget})",
            )
            placement = node.stack_placement
            if placement is not None and parent_type == NodeType.STACK:
                fields = positioned_fields_for_stack_center_fill(placement)
                return f"Positioned({', '.join(fields)}, child: {widget})"
            return widget
    if parent_node is not None and _is_skip_control_stack(parent_node):
        placement = node.stack_placement
        style_expr = text_style_expr(
            node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        text = escape_figma_text_literal(node)
        trailing = text_widget_trailing_params(
            node.style,
            text_align_suffix=", textAlign: TextAlign.center",
        )
        widget = f"Text('{text}', style: {style_expr}, {trailing})"
        widget = _wrap_accessibility(
            node_with_display_accessibility(node),
            f"Center(child: {widget})",
        )
        if placement is not None and parent_type == NodeType.STACK:
            fields = _positioned_fields(placement)
            _ensure_positioned_stack_bounds(fields, node, placement)
            numeral_top = _skip_control_numeral_top(parent_node, node, placement)
            fields = [
                field if not field.startswith("top:") else f"top: {numeral_top}" for field in fields
            ]
            return f"Positioned({', '.join(fields)}, child: {widget})"
        return widget
    node = _clamp_centered_text_to_parent_stack(node, parent_node)
    fill_parent = _should_center_in_parent_stack(node, parent_node)
    if parent_node is not None and layout_fact_stack_numeric_glyph_overlay_host(parent_node):
        fill_parent = False
    if fill_parent:
        widget = _wrap_centered_stack_child(node, widget)
    emit_node = node_with_display_accessibility(node)
    if not isinstance(emit_node, CleanDesignTreeNode):
        emit_node = node
    return _finalize_widget(
        emit_node,
        widget,
        parent_type=parent_type,
        parent_node=parent_node,
        fill_parent=fill_parent,
        scroll_content_root=scroll_content_root,
    )
