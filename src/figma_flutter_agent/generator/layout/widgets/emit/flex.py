"""ROW and COLUMN rendering branches."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import is_centered_glyph_badge
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


def render_row(node: CleanDesignTreeNode, ctx: dict, flow: dict, *, recurse) -> str:
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
        row_hosts_chip_beside_heading,
        row_is_status_pill_badge,
        row_is_tight_horizontal_pill_label,
    )
    from figma_flutter_agent.generator.layout.navigation.items import (
        row_hosts_compact_nav_tabs,
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
    if is_centered_glyph_badge(node) and len(node.children) == 1:
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
    if row_is_tight_horizontal_pill_label(node) and child_widgets:
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
        if width is not None and float(width) > 0:
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
    if row_is_status_pill_badge(node) and child_widgets:
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
        row_equal_metric_cards_cross_axis,
        wrap_equal_metric_cards_row_height,
    )

    body = flex_children_body(node, child_widgets, axis="horizontal")
    spacing_field = _flex_spacing_field(node)
    row_cross = row_equal_metric_cards_cross_axis(node, cross_axis=cross_axis)
    widget = (
        f"Row(mainAxisAlignment: {main_axis}, crossAxisAlignment: {row_cross}, "
        f"{spacing_field}children: [{body}])"
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


def render_column(node: CleanDesignTreeNode, ctx: dict, flow: dict) -> str:
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
        column_is_product_tile_metadata,
        row_is_status_pill_badge,
    )

    if column_is_product_tile_metadata(node, parent_node) and len(child_widgets) >= 2:
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
    if row_is_status_pill_badge(node) and child_widgets:
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
            column_is_tight_stack_text_host,
        )

        if (
            len(node.children) == 1
            and node.children[0].type == NodeType.TEXT
            and parent_type == NodeType.ROW
        ):
            widget = f"Align(alignment: Alignment.centerLeft, child: {body})"
        elif column_is_tight_stack_text_host(node):
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
                main_size_field = (
                    "mainAxisSize: MainAxisSize.min, "
                    if scroll_content_root
                    or _column_peer_in_bounded_row(node, parent_node=parent_node)
                    or _column_is_text_primary(node)
                    or column_in_bounded_positioned_host(node)
                    or _column_spaced_stack_sizes_intrinsically(node)
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
