"""ROW and COLUMN rendering branches."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import layout_fact_centered_glyph_badge
from figma_flutter_agent.generator.layout.responsive import (
    child_is_bottom_nav,
    should_apply_responsive_column_reflow,
    wrap_responsive_root_column,
)
from figma_flutter_agent.generator.layout.scroll import (
    render_both_axis_scroll,
    render_scroll_list,
    scroll_axis_for_list,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..button import _try_render_checkbox_label_row
from ..decoration import _wrap_widget_with_box_decoration
from ..finalize import _finalize_widget
from ..flex_sizing import flex_children_body
from ..hero import status_pill_badge_body, try_render_space_between_text_metric_row
from ..layout import _flex_spacing_field, _wrap_center_preserving_flex_parent_data
from ..position import _wrap_root_column_viewport
from ..svg import _render_exported_vector, _should_prefer_exported_svg
from ..thumbnail import try_render_oversized_photo_clip_column
from .context import LayoutRenderContext


def render_row(
    node: CleanDesignTreeNode,
    ctx: LayoutRenderContext,
    flow: dict,
    *,
    recurse,
) -> str:
    """Render a NodeType.ROW node."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    main_axis = flow["main_axis"]
    cross_axis = flow["cross_axis"]
    uses_svg = ctx["uses_svg"]
    theme_variant = ctx["theme_variant"]
    responsive_enabled = ctx["responsive_enabled"]
    design_artboard_width = ctx["design_artboard_width"]
    cluster_classes = ctx["cluster_classes"]
    cluster_vector_variants = ctx["cluster_vector_variants"]
    cluster_vector_variant = ctx["cluster_vector_variant"]
    skip_cluster_id = ctx["skip_cluster_id"]
    bundled_font_families = ctx["bundled_font_families"]
    dart_weight_overrides_by_family = ctx["dart_weight_overrides_by_family"]
    text_theme_slot_by_style_name = ctx["text_theme_slot_by_style_name"]
    text_theme_size_slots = ctx["text_theme_size_slots"]
    de_archetype_pass = ctx["de_archetype_pass"]

    if node.scroll_axis == "horizontal":
        widget = render_scroll_list(
            node,
            child_widgets,
            axis="horizontal",
            parent_type=parent_type,
            section_children=node.children,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    from figma_flutter_agent.generator.layout.flex_policy import (
        _row_usable_main_span,
        layout_fact_row_numeric_counter_badge,
        layout_fact_row_status_pill_badge,
        layout_fact_row_tight_horizontal_pill_label,
        row_hosts_chip_beside_heading,
    )
    from figma_flutter_agent.generator.layout.navigation.items import (
        row_hosts_compact_nav_tabs,
    )
    from figma_flutter_agent.generator.layout.widgets.button import _wrap_button_stack
    from figma_flutter_agent.parser.geometry import (
        auth_button_confidence,
        social_auth_icon_button_confidence,
        social_auth_row_confidence,
    )
    from figma_flutter_agent.parser.interaction import (
        button_hosts_horizontal_social_auth_icon_cluster,
    )
    from figma_flutter_agent.parser.interaction.text_actions import (
        layout_fact_primary_cta_painted_row_shell,
    )

    if button_hosts_horizontal_social_auth_icon_cluster(node) and child_widgets:
        wrapped: list[str] = []
        for child, widget in zip(node.children, child_widgets, strict=True):
            if (
                social_auth_row_confidence(child) >= 0.65
                or auth_button_confidence(child) >= 0.5
                or social_auth_icon_button_confidence(child) >= 0.65
            ):
                widget = _wrap_button_stack(
                    widget,
                    child,
                    theme_variant=theme_variant,
                )
            wrapped.append(widget)
        child_widgets = wrapped

    if layout_fact_primary_cta_painted_row_shell(node) and child_widgets:
        from figma_flutter_agent.generator.layout.flex_policy import (
            resolve_row_emit_spacing_body,
            row_equal_metric_cards_cross_axis,
        )

        spacing_field, body, _needs_fitted = resolve_row_emit_spacing_body(
            node,
            child_widgets,
            parent_node=parent_node,
        )
        row_cross = row_equal_metric_cards_cross_axis(node, cross_axis=cross_axis)
        row_inner = (
            f"Row(mainAxisAlignment: {main_axis}, crossAxisAlignment: {row_cross}, "
            f"{spacing_field}children: [{body}])"
        )
        widget = _wrap_button_stack(
            row_inner,
            node,
            theme_variant=theme_variant,
            tap_role="button-action",
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    checkbox_label_row = _try_render_checkbox_label_row(
        node,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if checkbox_label_row is not None:
        widget = _wrap_widget_with_box_decoration(
            node,
            checkbox_label_row,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    from figma_flutter_agent.generator.layout.widgets.input import (
        try_render_prefix_labeled_currency_row,
    )

    prefix_currency_row = try_render_prefix_labeled_currency_row(
        node,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if prefix_currency_row is not None:
        widget = _wrap_widget_with_box_decoration(
            node,
            prefix_currency_row,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    metric_row = try_render_space_between_text_metric_row(
        node,
        child_widgets=child_widgets,
        uses_svg=uses_svg,
        render_node_body=recurse,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if metric_row is not None:
        widget = _wrap_widget_with_box_decoration(
            node,
            metric_row,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if row_hosts_compact_nav_tabs(node):
        main_axis = "MainAxisAlignment.spaceAround"
    if row_hosts_chip_beside_heading(node) and child_widgets:
        spacing_field = _flex_spacing_field(node)
        body = ", ".join(child_widgets)
        widget = (
            "Align("
            "alignment: Alignment.centerLeft, "
            f"child: Row(mainAxisSize: MainAxisSize.min, "
            f"mainAxisAlignment: {main_axis}, "
            f"crossAxisAlignment: {cross_axis}, "
            f"{spacing_field}children: [{body}]))"
        )
        widget = _wrap_widget_with_box_decoration(
            node,
            widget,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if layout_fact_row_numeric_counter_badge(node) and child_widgets:
        body = status_pill_badge_body(
            node,
            child_widgets,
            main_axis=main_axis,
            cross_axis=cross_axis,
            flex_spacing_field=_flex_spacing_field,
        )
        widget = _wrap_widget_with_box_decoration(
            node,
            body,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if layout_fact_centered_glyph_badge(node) and len(node.children) == 1:
        text_body = recurse(
            node.children[0],
            uses_svg=uses_svg,
            parent_type=NodeType.ROW,
            parent_node=node,
            theme_variant=theme_variant,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            cluster_vector_variant=cluster_vector_variant,
            skip_cluster_id=skip_cluster_id,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
            de_archetype_pass=de_archetype_pass,
        )
        widget = _wrap_widget_with_box_decoration(
            node,
            _wrap_center_preserving_flex_parent_data(text_body),
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if layout_fact_row_tight_horizontal_pill_label(node) and child_widgets:
        from figma_flutter_agent.parser.interaction.inline_input_hosts import (
            layout_fact_phone_prefix_chrome_row,
        )
        from figma_flutter_agent.parser.interaction.chip_variant import (
            is_tag_component_chip_row,
        )

        if not layout_fact_phone_prefix_chrome_row(node):
            span = _row_usable_main_span(node)
            width = float(span) if span is not None and span > 0 else node.sizing.width
            if len(child_widgets) == 1:
                inner = child_widgets[0]
            else:
                spacing_field = _flex_spacing_field(node)
                inner = (
                    f"Row(mainAxisSize: MainAxisSize.min, "
                    "mainAxisAlignment: MainAxisAlignment.center, "
                    "crossAxisAlignment: CrossAxisAlignment.center, "
                    f"{spacing_field}children: [{', '.join(child_widgets)}])"
                )
            if width is not None and float(width) > 0 and not is_tag_component_chip_row(node):
                if node.style.background_color:
                    body = f"Center(child: {inner})"
                else:
                    width_lit = format_geometry_literal(float(width))
                    body = f"SizedBox(width: {width_lit}, child: Center(child: {inner}))"
            else:
                body = f"Center(child: {inner})"
            widget = _wrap_widget_with_box_decoration(
                node,
                body,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
                parent_node=parent_node,
            )
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
    if layout_fact_row_status_pill_badge(node) and child_widgets:
        body = status_pill_badge_body(
            node,
            child_widgets,
            main_axis=main_axis,
            cross_axis=cross_axis,
            flex_spacing_field=_flex_spacing_field,
        )
        widget = _wrap_widget_with_box_decoration(
            node,
            body,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if uses_svg and _should_prefer_exported_svg(node):
        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is not None:
            width = node.sizing.width
            height = node.sizing.height
            if width is not None and height is not None and width > 0 and height > 0:
                exported = (
                    f"SizedBox(width: {format_geometry_literal(width)}, "
                    f"height: {format_geometry_literal(height)}, "
                    f"child: {exported})"
                )
            spacing_field = _flex_spacing_field(node)
            widget = (
                f"Row(mainAxisAlignment: {main_axis}, "
                f"crossAxisAlignment: {cross_axis}, "
                f"{spacing_field}children: [{exported}])"
            )
            widget = _wrap_widget_with_box_decoration(
                node,
                widget,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
                parent_node=parent_node,
            )
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
    from figma_flutter_agent.generator.layout.flex_policy import (
        layout_fact_row_overflowing_painted_chip_strip,
        resolve_row_emit_spacing_body,
        row_equal_metric_cards_cross_axis,
        row_fitted_box_alignment,
        wrap_equal_metric_cards_row_height,
    )
    from figma_flutter_agent.generator.layout.scroll import wrap_horizontal_intrinsic_row_scroll

    spacing_field, body, needs_fitted = resolve_row_emit_spacing_body(
        node,
        child_widgets,
        parent_node=parent_node,
    )
    row_cross = row_equal_metric_cards_cross_axis(node, cross_axis=cross_axis)
    if needs_fitted:
        fitted_align = row_fitted_box_alignment(node)
        widget = (
            f"FittedBox(fit: BoxFit.scaleDown, alignment: {fitted_align}, "
            f"child: Row(mainAxisAlignment: {main_axis}, crossAxisAlignment: {row_cross}, "
            f"{spacing_field}children: [{body}]))"
        )
    else:
        widget = (
            f"Row(mainAxisAlignment: {main_axis}, crossAxisAlignment: {row_cross}, "
            f"{spacing_field}children: [{body}])"
        )
    if layout_fact_row_overflowing_painted_chip_strip(node, parent_node=parent_node):
        widget = wrap_horizontal_intrinsic_row_scroll(
            widget,
            height=node.sizing.height,
        )
    widget = wrap_equal_metric_cards_row_height(
        node,
        widget,
        parent_type=parent_type,
    )
    widget = _wrap_widget_with_box_decoration(
        node,
        widget,
        responsive_enabled=responsive_enabled,
        design_artboard_width=design_artboard_width,
        parent_node=parent_node,
    )
    return _finalize_widget(
        node,
        widget,
        parent_type=parent_type,
        parent_node=parent_node,
        scroll_content_root=scroll_content_root,
    )


def render_column(node: CleanDesignTreeNode, ctx: LayoutRenderContext, flow: dict) -> str:
    """Render a NodeType.COLUMN node."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    is_layout_root = flow["is_layout_root"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    main_axis = flow["main_axis"]
    cross_axis = flow["cross_axis"]
    theme_variant = ctx["theme_variant"]
    responsive_enabled = ctx["responsive_enabled"]
    design_artboard_width = ctx["design_artboard_width"]

    from figma_flutter_agent.generator.layout.flex_policy import (
        layout_fact_column_product_tile_metadata,
        layout_fact_row_status_pill_badge,
    )

    if layout_fact_column_product_tile_metadata(node, parent_node) and len(child_widgets) >= 2:
        spacing_field = _flex_spacing_field(node)
        body = (
            f"Column(crossAxisAlignment: {cross_axis}, "
            "mainAxisSize: MainAxisSize.min, "
            "mainAxisAlignment: MainAxisAlignment.start, "
            f"{spacing_field}children: [{', '.join(child_widgets)}])"
        )
        widget = _wrap_widget_with_box_decoration(
            node,
            body,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if layout_fact_row_status_pill_badge(node) and child_widgets:
        body = status_pill_badge_body(
            node,
            child_widgets,
            main_axis=main_axis,
            cross_axis=cross_axis,
            flex_spacing_field=_flex_spacing_field,
        )
        widget = _wrap_widget_with_box_decoration(
            node,
            body,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    photo_column = try_render_oversized_photo_clip_column(node)
    if photo_column is not None:
        widget = _wrap_widget_with_box_decoration(
            node,
            photo_column,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            parent_node=parent_node,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if node.scroll_axis == "both":
        widget = render_both_axis_scroll(
            node,
            child_widgets,
            parent_type=parent_type,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    scroll_axis = scroll_axis_for_list(node)
    responsive_bottom_nav_root = (
        responsive_enabled and bool(child_widgets) and child_is_bottom_nav(child_widgets[-1])
    )
    if scroll_axis is not None and not responsive_bottom_nav_root:
        widget = render_scroll_list(
            node,
            child_widgets,
            axis=scroll_axis,
            parent_type=parent_type,
            section_children=node.children,
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if should_apply_responsive_column_reflow(
        responsive_enabled=responsive_enabled,
        scroll_axis="none" if responsive_bottom_nav_root else node.scroll_axis,
        is_layout_root=is_layout_root,
        parent_type=parent_type,
        child_widgets=child_widgets,
        contains_form_control=any(child.type == NodeType.INPUT for child in node.children),
        design_artboard_width=design_artboard_width,
    ):
        widget = wrap_responsive_root_column(
            main_axis=main_axis,
            cross_axis=cross_axis,
            child_widgets=child_widgets,
            design_artboard_width=design_artboard_width,
            spacing_field=_flex_spacing_field(node),
        )
    else:
        body = flex_children_body(node, child_widgets, axis="vertical")
        from figma_flutter_agent.generator.layout.flex_policy import (
            _column_is_text_primary,
            _column_peer_in_bounded_row,
            _column_spaced_stack_sizes_intrinsically,
            column_cross_to_align_expr,
            column_in_bounded_positioned_host,
            layout_fact_column_tight_stack_text_host,
        )

        if (
            len(node.children) == 1
            and node.children[0].type == NodeType.TEXT
            and parent_type == NodeType.ROW
        ):
            widget = f"Align(alignment: Alignment.centerLeft, child: {body})"
        elif layout_fact_column_tight_stack_text_host(node):
            cross = node.alignment.cross
            if _column_is_text_primary(node) and all(
                child.type == NodeType.TEXT and (child.style.text_align or "LEFT").upper() == "LEFT"
                for child in node.children
            ):
                align = "Alignment.centerLeft"
            else:
                align = column_cross_to_align_expr(cross)
            widget = f"Align(alignment: {align}, child: {body})"
        else:
            from figma_flutter_agent.generator.layout.stack_chrome import (
                column_hoists_docked_bottom_nav_stack,
            )

            if (
                is_layout_root
                and column_hoists_docked_bottom_nav_stack(node)
                and len(node.children) == 1
            ):
                widget = body
            else:
                spacing_field = _flex_spacing_field(node)
                from figma_flutter_agent.parser.interaction.step import (
                    layout_fact_nav_stepper_row,
                    layout_fact_step_indicator_title_column,
                )

                if (
                    layout_fact_step_indicator_title_column(node)
                    and parent_node is not None
                    and layout_fact_nav_stepper_row(parent_node)
                ):
                    spacing_field = ""
                    body = flex_children_body(
                        node,
                        child_widgets,
                        axis="vertical",
                        explicit_gap_cap=8.0,
                    )
                from figma_flutter_agent.generator.layout.flex_policy.column import (
                    column_should_stretch_for_footer_pin,
                )

                stretch_footer = column_should_stretch_for_footer_pin(
                    node,
                    parent_node=parent_node,
                    scroll_content_root=scroll_content_root,
                )
                main_size_field = (
                    "mainAxisSize: MainAxisSize.min, "
                    if (
                        scroll_content_root
                        or _column_peer_in_bounded_row(node, parent_node=parent_node)
                        or _column_is_text_primary(node)
                        or column_in_bounded_positioned_host(node)
                        or _column_spaced_stack_sizes_intrinsically(node)
                    )
                    and not stretch_footer
                    else "mainAxisSize: MainAxisSize.max, "
                    if stretch_footer
                    else ""
                )
                widget = (
                    f"Column({main_size_field}mainAxisAlignment: {main_axis}, "
                    f"crossAxisAlignment: {cross_axis}, "
                    f"{spacing_field}children: [{body}])"
                )
    widget = _wrap_widget_with_box_decoration(
        node,
        widget,
        responsive_enabled=responsive_enabled,
        design_artboard_width=design_artboard_width,
        parent_node=parent_node,
    )
    if is_layout_root:
        widget = _wrap_root_column_viewport(
            node,
            widget,
            responsive_enabled=responsive_enabled,
            theme_variant=theme_variant,
        )
    return _finalize_widget(
        node,
        widget,
        parent_type=parent_type,
        parent_node=parent_node,
        scroll_content_root=scroll_content_root,
    )
