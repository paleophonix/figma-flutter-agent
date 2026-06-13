"""BUTTON and INPUT node rendering branches."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.form import (
    render_button,
    render_checkbox,
    render_input,
)
from figma_flutter_agent.generator.layout.scroll import wrap_flex_auto_layout_padding
from figma_flutter_agent.parser.interaction import (
    input_children_are_presentational,
    input_flex_value_text,
    input_trailing_chrome_nodes,
    looks_like_checkbox_control,
    looks_like_compact_icon_action_button,
    looks_like_favorite_icon_button,
    looks_like_info_icon_button,
    looks_like_plus_icon_button,
    looks_like_stroke_minus_icon,
    looks_like_stroke_plus_icon,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..button import _wrap_button_stack
from ..finalize import _finalize_widget
from ..flex_sizing import _button_list_tile_row_body
from ..input import (
    _find_icon_glyph_expr,
    _render_flex_input_with_trailing_chrome,
    _render_stack_input,
)
from ..layout import _wrap_center_preserving_flex_parent_data
from ..thumbnail import try_render_cart_thumbnail_button


def render_button_node(
    node: CleanDesignTreeNode,
    ctx: dict,
    flow: dict,
    *,
    recurse,
) -> str:
    """Render a NodeType.BUTTON node."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    uses_svg = ctx["uses_svg"]
    theme_variant = ctx["theme_variant"]
    bundled_font_families = ctx["bundled_font_families"]
    dart_weight_overrides_by_family = ctx["dart_weight_overrides_by_family"]
    text_theme_slot_by_style_name = ctx["text_theme_slot_by_style_name"]
    text_theme_size_slots = ctx["text_theme_size_slots"]

    cart_thumbnail = try_render_cart_thumbnail_button(
        node,
        uses_svg=uses_svg,
        render_node_body=recurse,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if cart_thumbnail is not None:
        label = escape_dart_string(node.accessibility_label or node.name)
        return _finalize_widget(
            node,
            f"Semantics(label: '{label}', child: {cart_thumbnail})",
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    is_compact_icon_button = (
        looks_like_compact_icon_action_button(node)
        or looks_like_favorite_icon_button(node)
        or looks_like_plus_icon_button(node)
        or looks_like_info_icon_button(node)
    )
    if is_compact_icon_button:
        glyph = _find_icon_glyph_expr(node)
        if looks_like_stroke_plus_icon(node) or looks_like_stroke_minus_icon(node) or (
            looks_like_plus_icon_button(node)
            or looks_like_favorite_icon_button(node)
            or looks_like_info_icon_button(node)
        ):
            tap_role = "button-action"
        else:
            tap_role = "back-nav"
        if glyph is not None:
            stack_body = (
                "Stack(clipBehavior: Clip.none, alignment: Alignment.center, "
                f"children: [{glyph}])"
            )
        else:
            icon_body = ", ".join(child_widgets)
            stack_body = (
                f"Stack(clipBehavior: Clip.none, alignment: Alignment.center, "
                f"children: [{icon_body}])"
            )
        width = node.sizing.width
        height = node.sizing.height
        if (
            width is not None
            and height is not None
            and width > 0
            and height > 0
        ):
            stack_body = (
                f"SizedBox("
                f"width: {format_geometry_literal(width)}, "
                f"height: {format_geometry_literal(height)}, "
                f"child: {stack_body})"
            )
        widget = _wrap_button_stack(
            stack_body,
            node,
            theme_variant=theme_variant,
            tap_role=tap_role,
        )
        label = escape_dart_string(node.accessibility_label or node.name or "Back")
        widget = f"Semantics(label: '{label}', child: {widget})"
    elif child_widgets:
        label = escape_dart_string(
            node.accessibility_label or node.text or node.name or "Button"
        )
        from figma_flutter_agent.generator.layout.widgets.selection import (
            try_render_payment_option_card_body,
        )
        from figma_flutter_agent.parser.geometry import (
            auth_button_confidence,
            social_auth_row_confidence,
        )
        from figma_flutter_agent.parser.interaction import (
            button_has_composite_row_body,
            button_has_list_tile_row_body,
            button_hosts_multiple_auth_rows,
            button_hosts_stacked_text_column,
            button_should_flow_as_column,
        )

        payment_card_body = try_render_payment_option_card_body(
            node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if payment_card_body is not None:
            stack_body = payment_card_body
        elif button_has_list_tile_row_body(node):
            stack_body = _button_list_tile_row_body(node, child_widgets)
        elif button_should_flow_as_column(node):
            from figma_flutter_agent.generator.layout.button_flow import (
                button_vertical_auto_layout_stack,
            )
            from figma_flutter_agent.generator.layout.flex_policy import (
                stack_child_ordinal_bottom,
                stack_child_ordinal_top,
                stack_flow_child_horizontal_wrap,
                stack_flow_child_vertical_extent_wrap,
                tree_children_are_vertically_sequential,
            )

            paired_circle_ids = flow["paired_circle_ids"]
            omit_child_ids = flow["omit_child_ids"]
            emitted_children = [
                child
                for child in flow["sorted_children"]
                if child.id not in paired_circle_ids and child.id not in omit_child_ids
            ]
            pairs = list(zip(emitted_children, child_widgets, strict=True))
            if tree_children_are_vertically_sequential(emitted_children):
                ordered_pairs = sorted(
                    pairs,
                    key=lambda pair: (stack_child_ordinal_top(pair[0]), pair[0].id),
                )
            else:
                ordered_pairs = pairs
            flow_parts: list[str] = []
            button_spacing = float(node.spacing or 0.0)
            use_column_spacing = (
                button_spacing > 0.0
                and button_vertical_auto_layout_stack(node)
                and not tree_children_are_vertically_sequential(emitted_children)
            )
            multiple_auth_rows = button_hosts_multiple_auth_rows(node)
            for index, (child, widget) in enumerate(ordered_pairs):
                if index > 0 and not use_column_spacing:
                    previous_child = ordered_pairs[index - 1][0]
                    gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(
                        previous_child
                    )
                    if gap > 0.5:
                        flow_parts.append(
                            f"SizedBox(height: {format_geometry_literal(gap)})"
                        )
                flow_widget = stack_flow_child_horizontal_wrap(child, widget)
                flow_widget = stack_flow_child_vertical_extent_wrap(
                    child, flow_widget, parent_node=node
                )
                if multiple_auth_rows and (
                    social_auth_row_confidence(child) >= 0.65
                    or auth_button_confidence(child) >= 0.5
                ):
                    flow_widget = _wrap_button_stack(
                        flow_widget,
                        child,
                        theme_variant=theme_variant,
                    )
                flow_parts.append(flow_widget)
            body = ", ".join(flow_parts) or "const SizedBox.shrink()"
            spacing_field = ""
            if use_column_spacing:
                spacing_field = (
                    f", spacing: {format_geometry_literal(button_spacing)}"
                )
            stack_body = (
                "Column("
                "mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.stretch"
                f"{spacing_field}, "
                f"children: [{body}]"
                ")"
            )
            if multiple_auth_rows:
                widget = f"Semantics(label: '{label}', child: {stack_body})"
                return _finalize_widget(
                    node,
                    widget,
                    parent_type=parent_type,
                    parent_node=parent_node,
                    scroll_content_root=scroll_content_root,
                )
        else:
            from figma_flutter_agent.generator.layout.flex_policy import (
                button_hosts_status_pill,
                button_is_pill_with_centered_label,
                button_should_fitted_box_label,
                horizontal_chip_button_should_hug_width,
            )

            if (
                len(child_widgets) == 1
                and len(node.children) == 1
                and node.children[0].type == NodeType.TEXT
            ):
                from figma_flutter_agent.parser.interaction import (
                    button_is_left_aligned_text_label,
                )

                body = child_widgets[0]
                if button_should_fitted_box_label(node):
                    body = (
                        "FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.center, "
                        f"child: {body})"
                    )
                if button_is_left_aligned_text_label(node):
                    body = f"Align(alignment: Alignment.centerLeft, child: {body})"
                else:
                    body = _wrap_center_preserving_flex_parent_data(body)
            else:
                body = ", ".join(child_widgets)
            stack_fit = (
                "StackFit.expand"
                if button_is_pill_with_centered_label(node)
                else (
                    "StackFit.loose"
                    if button_has_composite_row_body(node)
                    or button_hosts_stacked_text_column(node)
                    or horizontal_chip_button_should_hug_width(node)
                    or button_hosts_status_pill(node)
                    else "StackFit.expand"
                )
            )
            stack_body = (
                "Stack("
                "clipBehavior: Clip.none, "
                f"fit: {stack_fit}, "
                f"children: [{body}]"
                ")"
            )
        stack_body = wrap_flex_auto_layout_padding(node, stack_body)
        widget = _wrap_button_stack(
            stack_body,
            node,
            theme_variant=theme_variant,
        )
        widget = f"Semantics(label: '{label}', child: {widget})"
    else:
        widget = render_button(node, theme_variant=theme_variant)
    return _finalize_widget(
        node, widget, parent_type=parent_type, parent_node=parent_node,
        scroll_content_root=scroll_content_root,
    )


def render_input_node(node: CleanDesignTreeNode, ctx: dict, flow: dict) -> str:
    """Render a NodeType.INPUT node."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    cross_axis = flow["cross_axis"]
    uses_svg = ctx["uses_svg"]
    theme_variant = ctx["theme_variant"]
    bundled_font_families = ctx["bundled_font_families"]
    dart_weight_overrides_by_family = ctx["dart_weight_overrides_by_family"]
    text_theme_slot_by_style_name = ctx["text_theme_slot_by_style_name"]
    text_theme_size_slots = ctx["text_theme_size_slots"]

    if looks_like_checkbox_control(node):
        widget = render_checkbox(node, theme_variant=theme_variant)
        width = node.sizing.width
        height = node.sizing.height
        if width is not None and height is not None and width > 0 and height > 0:
            widget = f"SizedBox(width: {width}, height: {height}, child: {widget})"
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    trailing = input_trailing_chrome_nodes(node)
    if not trailing:
        for child in node.children:
            if child.type == NodeType.INPUT:
                trailing = input_trailing_chrome_nodes(child)
                if trailing:
                    break
    presentational = input_children_are_presentational(node)
    if child_widgets and not presentational:
        from figma_flutter_agent.generator.layout.widgets.flex_sizing import (
            _flex_spacing_field,
        )

        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        spacing_field = _flex_spacing_field(node)
        main_size_field = (
            "mainAxisSize: MainAxisSize.min, " if node.spacing > 0 else ""
        )
        widget = (
            f"Column({main_size_field}crossAxisAlignment: {cross_axis}, "
            f"{spacing_field}children: [{body}])"
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if child_widgets and presentational:
        if trailing and input_flex_value_text(node) is not None:
            return _render_flex_input_with_trailing_chrome(
                node,
                trailing,
                theme_variant=theme_variant,
                parent_type=parent_type,
                uses_svg=uses_svg,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
        return _render_stack_input(
            node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
            trailing_nodes=trailing or None,
            uses_svg=uses_svg,
        )
    widget = render_input(node, theme_variant=theme_variant)
    return _finalize_widget(
        node, widget, parent_type=parent_type, parent_node=parent_node,
        scroll_content_root=scroll_content_root,
    )
