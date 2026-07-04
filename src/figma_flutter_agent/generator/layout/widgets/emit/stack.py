"""STACK rendering branch and the logo-wordmark stack archetype."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_back_nav_stack as cupertino_wrap_back_nav_stack,
)
from figma_flutter_agent.generator.layout.style import box_decoration_expr
from figma_flutter_agent.parser.interaction import (
    is_back_navigation_icon_stack,
    layout_fact_back_nav_stack,
    layout_fact_skip_control_stack,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.parser.render_bounds import stack_needs_soft_clip
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..button import _wrap_button_stack
from ..finalize import _finalize_widget
from ..hero import (
    try_render_compact_icon_label_metric_stack,
    try_render_detail_hero_banner_stack,
    try_render_metric_icon_label_band_row,
    try_render_product_recommendation_hero_stack,
)
from ..input import _render_stack_input
from ..playback import (
    _try_render_play_pause_stack,
    _try_render_pruned_cluster_skip_control,
)
from ..position import _wrap_root_stack_viewport
from ..thumbnail import (
    try_render_compact_raster_photo_stack,
    try_render_media_avatar_stack,
    try_render_square_product_photo_stack,
)


def _stack_child_left(child: CleanDesignTreeNode) -> float:
    if child.stack_placement is not None and child.stack_placement.left is not None:
        return float(child.stack_placement.left)
    return float(child.offset_x)


def _is_logo_wordmark_stack(node: CleanDesignTreeNode) -> bool:
    if node.type != NodeType.STACK or len(node.children) != 3:
        return False
    texts = [child for child in node.children if child.type == NodeType.TEXT]
    if len(texts) != 2:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if node.stack_placement is not None:
        if node.stack_placement.width is not None:
            width = node.stack_placement.width
        if node.stack_placement.height is not None:
            height = node.stack_placement.height
    return width is not None and height is not None and width <= 220.0 and height <= 48.0


def _is_vector_logo_mark_stack(node: CleanDesignTreeNode) -> bool:
    """Compact icon + vector wordmark stacks with absolute vector children."""
    if node.type != NodeType.STACK or len(node.children) != 2:
        return False
    from ..svg import stack_should_emit_flattened_vector_group

    if (
        node.vector_asset_key
        and node.vector_asset_key.endswith(".svg")
        and stack_should_emit_flattened_vector_group(node)
    ):
        return False
    if not all(child.type == NodeType.VECTOR for child in node.children):
        return False
    if not all(child.stack_placement is not None for child in node.children):
        return False
    width, height = _logo_wordmark_stack_size(node)
    return width > 0 and height > 0 and width <= 220.0 and height <= 48.0


def _logo_wordmark_stack_size(node: CleanDesignTreeNode) -> tuple[float, float]:
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    if node.stack_placement is not None:
        if node.stack_placement.width is not None:
            width = float(node.stack_placement.width)
        if node.stack_placement.height is not None:
            height = float(node.stack_placement.height)
    return width, height


def _render_logo_wordmark_stack(
    node: CleanDesignTreeNode, ctx: dict[str, Any], *, recurse: Callable[..., str]
) -> str:
    width, height = _logo_wordmark_stack_size(node)
    child_widgets = [
        recurse(
            child,
            uses_svg=ctx["uses_svg"],
            parent_type=NodeType.STACK,
            parent_node=node,
            theme_variant=ctx["theme_variant"],
            cluster_classes=ctx["cluster_classes"],
            cluster_vector_variants=ctx["cluster_vector_variants"],
            cluster_vector_variant=ctx["cluster_vector_variant"],
            skip_cluster_id=ctx["skip_cluster_id"],
            responsive_enabled=ctx["responsive_enabled"],
            design_artboard_width=ctx["design_artboard_width"],
            bundled_font_families=ctx["bundled_font_families"],
            dart_weight_overrides_by_family=ctx["dart_weight_overrides_by_family"],
            text_theme_slot_by_style_name=ctx["text_theme_slot_by_style_name"],
            text_theme_size_slots=ctx["text_theme_size_slots"],
        )
        for child in sorted(node.children, key=_stack_child_left)
    ]
    return (
        f"SizedBox("
        f"width: {format_geometry_literal(width)}, "
        f"height: {format_geometry_literal(height)}, "
        f"child: Stack(clipBehavior: Clip.none, children: [{', '.join(child_widgets)}])"
        ")"
    )


def _render_vector_logo_mark_stack(
    node: CleanDesignTreeNode, ctx: dict[str, Any], *, recurse: Callable[..., str]
) -> str:
    """Emit positioned vector icon + wordmark inside a bounded logo stack."""
    width, height = _logo_wordmark_stack_size(node)
    child_widgets: list[str] = []
    for child in sorted(node.children, key=_stack_child_left):
        child_widgets.append(
            recurse(
                child,
                uses_svg=ctx["uses_svg"],
                parent_type=NodeType.STACK,
                parent_node=node,
                theme_variant=ctx["theme_variant"],
                cluster_classes=ctx["cluster_classes"],
                cluster_vector_variants=ctx["cluster_vector_variants"],
                cluster_vector_variant=ctx["cluster_vector_variant"],
                skip_cluster_id=ctx["skip_cluster_id"],
                responsive_enabled=ctx["responsive_enabled"],
                design_artboard_width=ctx["design_artboard_width"],
                bundled_font_families=ctx["bundled_font_families"],
                dart_weight_overrides_by_family=ctx["dart_weight_overrides_by_family"],
                text_theme_slot_by_style_name=ctx["text_theme_slot_by_style_name"],
                text_theme_size_slots=ctx["text_theme_size_slots"],
            )
        )
    return (
        f"SizedBox("
        f"width: {format_geometry_literal(width)}, "
        f"height: {format_geometry_literal(height)}, "
        f"child: Stack(clipBehavior: Clip.none, children: [{', '.join(child_widgets)}])"
        ")"
    )


def render_stack(
    node: CleanDesignTreeNode,
    ctx: dict[str, Any],
    flow: dict[str, Any],
    *,
    recurse: Callable[..., str],
) -> str:
    """Render a NodeType.STACK node (the non-early-return path)."""
    parent_type = flow["parent_type"]
    parent_node = flow["parent_node"]
    is_layout_root = flow["is_layout_root"]
    scroll_content_root = flow["scroll_content_root"]
    child_widgets = flow["child_widgets"]
    sorted_children = flow["sorted_children"]
    emitted_pairs: list[tuple[CleanDesignTreeNode, str]] = flow["emitted_pairs"]
    metadata_column_host = flow["metadata_column_host"]
    paired_circle_ids = flow["paired_circle_ids"]
    omit_child_ids = flow["omit_child_ids"]
    playback_seek_ids = flow["playback_seek_ids"]
    playback_decor_omit_ids = flow["playback_decor_omit_ids"]
    playback_seek_widget = flow["playback_seek_widget"]
    uses_svg = ctx["uses_svg"]
    theme_variant = ctx["theme_variant"]
    skip_cluster_id = ctx["skip_cluster_id"]
    cluster_vector_variant = ctx["cluster_vector_variant"]
    responsive_enabled = ctx["responsive_enabled"]
    bundled_font_families = ctx["bundled_font_families"]
    dart_weight_overrides_by_family = ctx["dart_weight_overrides_by_family"]
    text_theme_slot_by_style_name = ctx["text_theme_slot_by_style_name"]
    text_theme_size_slots = ctx["text_theme_size_slots"]

    from figma_flutter_agent.generator.layout.widgets.purchase_footer import (
        emit_purchase_footer_flow_layout,
        stack_should_flow_as_purchase_footer_band,
    )

    if stack_should_flow_as_purchase_footer_band(
        node,
        parent_type=parent_type,
        is_layout_root=is_layout_root,
    ):
        chrome_pairs: list[tuple[CleanDesignTreeNode, str]] = []
        for child in sorted_children:
            if (
                child.id in paired_circle_ids
                or child.id in omit_child_ids
                or child.id in playback_seek_ids
                or child.id in playback_decor_omit_ids
            ):
                continue
            chrome_pairs.append(
                (
                    child,
                    recurse(
                        child,
                        uses_svg=uses_svg,
                        parent_type=NodeType.ROW,
                        parent_node=node,
                        theme_variant=theme_variant,
                        cluster_classes=ctx.cluster_classes,
                        cluster_vector_variants=ctx.cluster_vector_variants,
                        cluster_vector_variant=cluster_vector_variant,
                        skip_cluster_id=skip_cluster_id,
                        responsive_enabled=responsive_enabled,
                        design_artboard_width=ctx.design_artboard_width,
                        bundled_font_families=bundled_font_families,
                        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                        text_theme_size_slots=text_theme_size_slots,
                    ),
                )
            )
        stack_widget = emit_purchase_footer_flow_layout(node, chrome_pairs)
        return _finalize_widget(
            node,
            stack_widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    from figma_flutter_agent.generator.layout.scroll import (
        horizontal_scroll_item_carrier,
        render_scroll_list,
    )

    scroll_carrier = horizontal_scroll_item_carrier(node)
    if scroll_carrier is not None and len(scroll_carrier.children) >= 2:
        carrier_widgets: list[str] = []
        for child in scroll_carrier.children:
            carrier_widgets.append(
                recurse(
                    child,
                    uses_svg=uses_svg,
                    parent_type=scroll_carrier.type,
                    parent_node=scroll_carrier,
                    theme_variant=theme_variant,
                    cluster_classes=ctx["cluster_classes"],
                    cluster_vector_variants=ctx["cluster_vector_variants"],
                    cluster_vector_variant=cluster_vector_variant,
                    skip_cluster_id=skip_cluster_id,
                    responsive_enabled=responsive_enabled,
                    design_artboard_width=ctx["design_artboard_width"],
                    bundled_font_families=bundled_font_families,
                    dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                    text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                    text_theme_size_slots=text_theme_size_slots,
                )
            )
        scroll_widget = render_scroll_list(
            scroll_carrier,
            carrier_widgets,
            axis="horizontal",
            parent_type=parent_type,
            section_children=scroll_carrier.children,
        )
        return _finalize_widget(
            node,
            scroll_widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    from figma_flutter_agent.assets.composite_icons import (
        is_composite_icon_export_node,
        layout_fact_compact_vector_icon_export_node,
    )
    from figma_flutter_agent.generator.layout.flex_policy import (
        stack_hosts_notification_badge_overlay,
    )
    from figma_flutter_agent.parser.interaction import (
        find_raster_photo_leaf,
        layout_fact_interactive_checkbox_control,
    )

    from ..svg import (
        _render_svg_picture,
        _should_center_in_parent_stack,
        _wrap_centered_stack_child,
    )

    has_raster_photo_fill = find_raster_photo_leaf(node) is not None
    if layout_fact_interactive_checkbox_control(node, parent_node=parent_node):
        from figma_flutter_agent.generator.layout.form import render_checkbox

        widget = render_checkbox(node, theme_variant=theme_variant)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if has_raster_photo_fill:
        compact_photo = try_render_media_avatar_stack(node, uses_svg=uses_svg)
        if compact_photo is None:
            compact_photo = try_render_compact_raster_photo_stack(node, uses_svg=uses_svg)
        if compact_photo is not None:
            return _finalize_widget(
                node,
                compact_photo,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
    if (
        uses_svg
        and node.vector_asset_key
        and not has_raster_photo_fill
        and not stack_hosts_notification_badge_overlay(node)
        and (
            is_composite_icon_export_node(node) or layout_fact_compact_vector_icon_export_node(node)
        )
    ):
        widget = _render_svg_picture(
            node,
            escape_dart_string(node.vector_asset_key),
        )
        fill_parent = _should_center_in_parent_stack(node, parent_node)
        if fill_parent:
            widget = _wrap_centered_stack_child(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
        )
    play_pause = _try_render_play_pause_stack(node)
    if play_pause is not None:
        label = escape_dart_string(node.accessibility_label or node.name)
        play_pause = _wrap_button_stack(play_pause, node, theme_variant=theme_variant)
        play_pause = f"Semantics(label: '{label}', child: {play_pause})"
        return _finalize_widget(
            node, play_pause, parent_type=parent_type, scroll_content_root=scroll_content_root
        )
    photo_stack = try_render_detail_hero_banner_stack(
        node,
        uses_svg=uses_svg,
        render_node_body=recurse,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if photo_stack is None:
        photo_stack = try_render_product_recommendation_hero_stack(
            node,
            uses_svg=uses_svg,
            render_node_body=recurse,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    if photo_stack is None:
        photo_stack = try_render_square_product_photo_stack(
            node,
            parent_node=parent_node,
            uses_svg=uses_svg,
            render_node_body=recurse,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    if photo_stack is not None:
        return _finalize_widget(
            node,
            photo_stack,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    metric_band = try_render_metric_icon_label_band_row(
        node,
        uses_svg=uses_svg,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if metric_band is not None:
        return _finalize_widget(
            node,
            metric_band,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    metric_stack = try_render_compact_icon_label_metric_stack(
        node,
        uses_svg=uses_svg,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if metric_stack is not None:
        return _finalize_widget(
            node,
            metric_stack,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    from figma_flutter_agent.generator.layout.widgets.stepper import (
        render_compact_quantity_stepper_stack,
    )
    from figma_flutter_agent.parser.interaction import layout_fact_stack_compact_quantity_stepper

    if layout_fact_stack_compact_quantity_stepper(node):
        compact_stepper = render_compact_quantity_stepper_stack(node, uses_svg=uses_svg)
        if compact_stepper is not None:
            return _finalize_widget(
                node,
                compact_stepper,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
    from figma_flutter_agent.generator.ir.context import IrEmitContext
    from figma_flutter_agent.generator.layout.choice_chip_row import (
        circular_chip_row_host_section_labels,
        circular_chip_row_section_labels_overlap_chips,
        layout_fact_circular_option_chip_row_host,
        render_circular_chip_row_host_shell,
        render_circular_option_chip_row_stateful,
    )

    if layout_fact_circular_option_chip_row_host(node) and not is_layout_root:
        chip_row = render_circular_option_chip_row_stateful(
            node,
            ctx=IrEmitContext(
                uses_svg=uses_svg,
                theme_variant=theme_variant,
                responsive_enabled=responsive_enabled,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            ),
        )
        section_labels = circular_chip_row_host_section_labels(node)
        if section_labels:
            ordered_labels = sorted(
                section_labels,
                key=lambda item: (
                    float(item.stack_placement.top or 0.0)
                    if item.stack_placement is not None
                    else 0.0
                ),
            )
            labels_overlap_chips = circular_chip_row_section_labels_overlap_chips(
                node,
                ordered_labels,
            )
            label_parent_type = NodeType.STACK if labels_overlap_chips else NodeType.COLUMN
            label_widgets = [
                recurse(
                    label,
                    uses_svg=uses_svg,
                    parent_type=label_parent_type,
                    parent_node=node,
                    theme_variant=theme_variant,
                    cluster_classes=ctx["cluster_classes"],
                    cluster_vector_variants=ctx["cluster_vector_variants"],
                    cluster_vector_variant=cluster_vector_variant,
                    skip_cluster_id=skip_cluster_id,
                    responsive_enabled=responsive_enabled,
                    design_artboard_width=ctx["design_artboard_width"],
                    bundled_font_families=bundled_font_families,
                    dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                    text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                    text_theme_size_slots=text_theme_size_slots,
                )
                for label in ordered_labels
            ]
            chip_body = render_circular_chip_row_host_shell(
                node,
                chip_row=chip_row,
                label_widgets=label_widgets,
                section_labels=ordered_labels,
            )
        else:
            chip_body = chip_row
        return _finalize_widget(
            node,
            chip_body,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    pruned_skip = _try_render_pruned_cluster_skip_control(
        node,
        uses_svg=uses_svg,
        skip_cluster_id=skip_cluster_id,
        cluster_vector_variant=cluster_vector_variant,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if pruned_skip is not None:
        label = escape_dart_string(node.accessibility_label or node.name)
        pruned_skip = f"Semantics(label: '{label}', child: {pruned_skip})"
        return _finalize_widget(
            node, pruned_skip, parent_type=parent_type, scroll_content_root=scroll_content_root
        )
    if not is_layout_root and layout_fact_back_nav_stack(node):
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        stack_widget = f"Stack(clipBehavior: Clip.none, children: [{body}])"
        if is_back_navigation_icon_stack(node):
            stack_widget = cupertino_wrap_back_nav_stack(
                stack_widget,
                theme_variant=theme_variant,
                node_id=node.id,
            )
        else:
            stack_widget = _wrap_button_stack(
                stack_widget,
                node,
                theme_variant=theme_variant,
            )
        return _finalize_widget(
            node,
            stack_widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    if not is_layout_root and layout_fact_skip_control_stack(node):
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        stack_widget = f"Stack(clipBehavior: Clip.none, children: [{body}])"
        label = escape_dart_string(node.accessibility_label or node.name)
        stack_widget = _wrap_button_stack(
            stack_widget,
            node,
            theme_variant=theme_variant,
        )
        stack_widget = f"Semantics(label: '{label}', child: {stack_widget})"
        return _finalize_widget(
            node,
            stack_widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    from figma_flutter_agent.generator.layout.widgets.button.checkbox_rows import (
        _try_render_checkbox_label_row,
    )

    checkbox_row = _try_render_checkbox_label_row(
        node,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if checkbox_row is not None:
        return _finalize_widget(
            node,
            checkbox_row,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )
    from figma_flutter_agent.parser.interaction.absolute_fields import (
        find_field_shell_external_label,
        find_field_shell_value_text,
        field_shell_external_label_gap,
        layout_fact_labeled_absolute_field_stack,
        layout_fact_painted_field_shell_container,
    )

    from ..input.absolute_fields import render_decomposed_absolute_field
    from ..input.fields import _compose_external_label_input

    if layout_fact_labeled_absolute_field_stack(node):
        shell = next(
            child for child in node.children if layout_fact_painted_field_shell_container(child)
        )
        value_node = find_field_shell_value_text(
            shell,
            node.children,
            host_height=node.sizing.height,
        )
        label_node = find_field_shell_external_label(
            shell,
            node.children,
            host_height=node.sizing.height,
        )
        if value_node is not None and label_node is not None:
            field = render_decomposed_absolute_field(
                shell,
                value_node,
                theme_variant=theme_variant,
                parent_type=NodeType.COLUMN,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
                flow_column_child=True,
            )
            composed = _compose_external_label_input(
                node,
                field,
                label_node=label_node,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
                label_field_gap=field_shell_external_label_gap(
                    shell,
                    node.children,
                    host_height=node.sizing.height,
                ),
            )
            return _finalize_widget(
                node,
                composed,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )
    interaction = None if is_layout_root else stack_interaction_kind(node)
    if interaction == "input":
        from figma_flutter_agent.parser.interaction.product import (
            layout_fact_checkout_sticky_footer_host,
            layout_fact_stack_product_purchase_footer_panel,
        )

        if layout_fact_stack_product_purchase_footer_panel(
            node
        ) or layout_fact_checkout_sticky_footer_host(node):
            interaction = None
    if interaction == "input":
        return _render_stack_input(
            node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    stack_children = list(child_widgets)
    if playback_seek_widget is not None:
        stack_children.append(playback_seek_widget)
    viewport_pinned_layers: list[str] | None = None
    preview_stack_widget: str | None = None
    body = ", ".join(stack_children) or "const SizedBox.shrink()"
    from figma_flutter_agent.generator.layout.flex_policy import (
        column_center_hug_child_wrap,
        column_child_should_center_hug,
        stack_child_ordinal_bottom,
        stack_child_ordinal_left,
        stack_child_ordinal_top,
        stack_flow_child_horizontal_wrap,
        stack_flow_child_vertical_extent_wrap,
        stack_pill_button_wrap_spacing,
        stack_should_emit_coalesced_inflow_fallback,
        stack_should_emit_mixed_inflow_column_overlay,
        stack_should_flow_as_centered_wrap,
        stack_should_flow_as_column,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_stack_tab_switcher_host,
    )
    from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
        stack_should_flow_as_tag_option_wrap,
    )

    if layout_fact_stack_tab_switcher_host(node):
        from figma_flutter_agent.generator.layout.widgets.emit.tab_switcher import (
            emit_tab_switcher_stack_children,
        )

        stack_widget = emit_tab_switcher_stack_children(
            node,
            emitted_pairs=emitted_pairs,
        )
    elif stack_should_flow_as_centered_wrap(node) or stack_should_flow_as_tag_option_wrap(node):
        ordered_pairs = sorted(
            emitted_pairs,
            key=lambda pair: (
                stack_child_ordinal_top(pair[0]),
                stack_child_ordinal_left(pair[0]),
                pair[0].id,
            ),
        )
        spacing_lit = format_geometry_literal(stack_pill_button_wrap_spacing(node.children))
        wrap_flow_parts = [widget for _, widget in ordered_pairs]
        body = ", ".join(wrap_flow_parts) or "const SizedBox.shrink()"
        stack_widget = (
            "Wrap("
            "alignment: WrapAlignment.start, "
            "runAlignment: WrapAlignment.start, "
            f"spacing: {spacing_lit}, "
            f"runSpacing: {spacing_lit}, "
            f"children: [{body}]"
            ")"
        )
    elif stack_should_flow_as_column(node):
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            _stack_is_phone_shell_layout,
            is_viewport_chrome_band,
            stack_child_is_growable_panel,
            stack_flow_child_is_shared_scroll_body,
            stack_flow_column_child_sort_key,
            stack_uses_shared_body_scroll_host,
        )
        from figma_flutter_agent.generator.layout.stack_chrome import (
            bottom_chrome_clearance_height,
            is_bottom_docked_stack_child,
        )
        from figma_flutter_agent.generator.layout.widgets.positioned import (
            _stack_has_bottom_anchored_child,
        )

        pin_bottom_chrome = _stack_has_bottom_anchored_child(node)
        allow_outward_paint = stack_needs_soft_clip(node)
        bottom_padding = bottom_chrome_clearance_height(node) if pin_bottom_chrome else 0.0
        growable_panels = sum(
            1 for child in sorted_children if stack_child_is_growable_panel(child)
        )
        is_phone_shell = _stack_is_phone_shell_layout(
            node,
            growable_panels=growable_panels,
        )
        uses_shared_scroll = pin_bottom_chrome and stack_uses_shared_body_scroll_host(
            node, growable_panels=growable_panels
        )
        ordered_pairs = sorted(
            emitted_pairs,
            key=lambda pair: stack_flow_column_child_sort_key(pair[0]),
        )
        column_flow_parts: list[str] = []
        scroll_body_parts: list[str] = []
        trailing_parts: list[str] = []
        for index, (child, widget) in enumerate(ordered_pairs):
            gap_expr: str | None = None
            if index > 0:
                previous_child = ordered_pairs[index - 1][0]
                gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(previous_child)
                if gap > 0.5:
                    gap_expr = f"SizedBox(height: {format_geometry_literal(gap)})"
            flow_widget = widget
            flow_widget = stack_flow_child_horizontal_wrap(child, flow_widget, parent_node=node)
            from figma_flutter_agent.generator.layout.flex_policy.stack import (
                stack_child_should_use_pin_bottom_scroll_host,
                stack_flow_child_needs_vertical_extent_bind,
            )
            from figma_flutter_agent.generator.layout.stack_chrome import (
                pin_bottom_flow_column_scroll_wrap,
            )

            if stack_flow_child_needs_vertical_extent_bind(
                child,
                parent_node=node,
                responsive_enabled=responsive_enabled,
            ):
                flow_widget = stack_flow_child_vertical_extent_wrap(
                    child, flow_widget, parent_node=node
                )
            is_scroll_body = uses_shared_scroll and stack_flow_child_is_shared_scroll_body(
                child, node
            )
            is_trailing = uses_shared_scroll and is_bottom_docked_stack_child(child)
            if not uses_shared_scroll:
                if (
                    pin_bottom_chrome
                    and responsive_enabled
                    and not is_bottom_docked_stack_child(child)
                    and not is_viewport_chrome_band(child)
                    and stack_child_should_use_pin_bottom_scroll_host(child, parent_stack=node)
                ):
                    flow_widget = pin_bottom_flow_column_scroll_wrap(
                        flow_widget,
                        allow_outward_paint=allow_outward_paint,
                        bottom_padding=bottom_padding,
                    )
                if (
                    responsive_enabled
                    and is_phone_shell
                    and not is_viewport_chrome_band(child)
                    and stack_child_is_growable_panel(child)
                    and "Expanded(" not in flow_widget
                ):
                    flow_widget = f"Expanded(child: {flow_widget})"
            if column_child_should_center_hug(node, child):
                flow_widget = column_center_hug_child_wrap(node, child, flow_widget)
            from figma_flutter_agent.generator.layout.flex_policy.wrap import (
                repair_flex_parent_data_order,
            )

            flow_widget = repair_flex_parent_data_order(flow_widget)
            if is_scroll_body:
                if gap_expr is not None:
                    scroll_body_parts.append(gap_expr)
                scroll_body_parts.append(flow_widget)
            elif is_trailing:
                if gap_expr is not None:
                    trailing_parts.append(gap_expr)
                trailing_parts.append(flow_widget)
            else:
                if gap_expr is not None:
                    column_flow_parts.append(gap_expr)
                column_flow_parts.append(flow_widget)
        if uses_shared_scroll and scroll_body_parts:
            inner_body = ", ".join(scroll_body_parts) or "const SizedBox.shrink()"
            inner_column = (
                "Column(mainAxisSize: MainAxisSize.min, "
                f"crossAxisAlignment: CrossAxisAlignment.stretch, children: [{inner_body}])"
            )
            column_flow_parts.append(
                pin_bottom_flow_column_scroll_wrap(
                    inner_column,
                    allow_outward_paint=allow_outward_paint,
                    bottom_padding=bottom_padding,
                )
            )
        column_flow_parts.extend(trailing_parts)
        body = ", ".join(column_flow_parts) or "const SizedBox.shrink()"
        main_axis = (
            "mainAxisSize: MainAxisSize.max, "
            if (pin_bottom_chrome or is_phone_shell) and responsive_enabled
            else "mainAxisSize: MainAxisSize.min, "
        )
        stack_widget = (
            f"Column({main_axis}crossAxisAlignment: CrossAxisAlignment.stretch, children: [{body}])"
        )
    elif stack_should_emit_mixed_inflow_column_overlay(
        node
    ) or stack_should_emit_coalesced_inflow_fallback(node):
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            stack_child_is_absolute_overlay,
            stack_flow_column_child_sort_key,
            stack_should_emit_coalesced_inflow_fallback,
            stack_should_emit_mixed_inflow_column_overlay,
        )
        from figma_flutter_agent.generator.layout.flex_policy.wrap import (
            repair_flex_parent_data_order,
        )

        ordered_pairs = sorted(
            emitted_pairs,
            key=lambda pair: stack_flow_column_child_sort_key(pair[0]),
        )
        widget_by_child_id: dict[str, str] = {}
        inflow_children: list[CleanDesignTreeNode] = []

        for child, widget in ordered_pairs:
            if stack_child_is_absolute_overlay(child):
                widget_by_child_id[child.id] = repair_flex_parent_data_order(widget)
                continue
            flow_widget = stack_flow_child_horizontal_wrap(child, widget, parent_node=node)
            if column_child_should_center_hug(node, child):
                flow_widget = column_center_hug_child_wrap(node, child, flow_widget)
            widget_by_child_id[child.id] = repair_flex_parent_data_order(flow_widget)
            inflow_children.append(child)

        segments: list[str] = []
        column_emitted = False
        background_overlays: list[str] = []
        foreground_overlays: list[str] = []
        from figma_flutter_agent.generator.background.detection import (
            is_decorative_absolute_background_overlay,
        )

        if inflow_children:
            inflow_children.sort(key=stack_flow_column_child_sort_key)
            spacing_field = ""
            if (node.spacing or 0.0) > 0.0 and len(inflow_children) >= 2:
                spacing_field = f"spacing: {format_geometry_literal(node.spacing)}, "
            inflow_body = (
                ", ".join(widget_by_child_id[child.id] for child in inflow_children)
                or "const SizedBox.shrink()"
            )
            inflow_column = (
                "Column("
                "mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.stretch, "
                f"{spacing_field}"
                f"children: [{inflow_body}]"
                ")"
            )
            from figma_flutter_agent.generator.layout.flex_policy.column import (
                wrap_fixed_card_inflow_column,
            )

            inflow_column = wrap_fixed_card_inflow_column(node, inflow_column)
        else:
            inflow_column = ""

        for child in node.children:
            if stack_child_is_absolute_overlay(child):
                widget = widget_by_child_id[child.id]
                if is_decorative_absolute_background_overlay(child):
                    background_overlays.append(widget)
                else:
                    foreground_overlays.append(widget)
            elif not column_emitted and inflow_column:
                column_emitted = True

        segments = [*background_overlays]
        if inflow_column:
            segments.append(inflow_column)
        segments.extend(foreground_overlays)

        body = ", ".join(segments) or "const SizedBox.shrink()"
        stack_clip = (
            "Clip.none" if not is_layout_root or stack_needs_soft_clip(node) else "Clip.hardEdge"
        )
        stack_widget = f"Stack(clipBehavior: {stack_clip}, children: [{body}])"
    elif metadata_column_host:
        spacing_field = ""
        if len(stack_children) >= 2:
            from figma_flutter_agent.generator.layout.flex_policy import (
                stack_child_ordinal_top,
            )

            ordered = sorted(
                node.children,
                key=lambda child: (stack_child_ordinal_top(child), child.id),
            )
            if len(ordered) >= 2:
                first = ordered[0]
                second = ordered[1]
                first_height = first.sizing.height or 0.0
                gap = stack_child_ordinal_top(second) - (
                    stack_child_ordinal_top(first) + first_height
                )
                if gap > 0:
                    spacing_field = f"spacing: {format_geometry_literal(gap)}, "
        stack_widget = (
            "Column("
            "mainAxisSize: MainAxisSize.min, "
            "crossAxisAlignment: CrossAxisAlignment.end, "
            f"{spacing_field}"
            f"children: [{body}]"
            ")"
        )
        from figma_flutter_agent.generator.layout.navigation.items import (
            layout_fact_stack_bottom_nav_tab_glyph_column,
        )

        if layout_fact_stack_bottom_nav_tab_glyph_column(node):
            stack_widget = (
                "Column("
                "mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.center, "
                f"{spacing_field}"
                f"children: [{body}]"
                ")"
            )
    else:
        from figma_flutter_agent.generator.layout.stack_chrome import (
            apply_pin_bottom_chrome_to_stack_layers,
            partition_viewport_pinned_stack_layers,
        )

        stack_emit_pairs = list(emitted_pairs)
        if stack_emit_pairs:
            stack_emit_children = [child for child, _ in stack_emit_pairs]
            stack_emit_widgets = [widget for _, widget in stack_emit_pairs]
            stack_children = apply_pin_bottom_chrome_to_stack_layers(
                node,
                stack_emit_children,
                stack_emit_widgets,
                allow_outward_paint=stack_needs_soft_clip(node),
            )
            if is_layout_root:
                partition = partition_viewport_pinned_stack_layers(
                    node,
                    stack_emit_children,
                    stack_children,
                )
                if partition is not None:
                    scroll_widgets, viewport_pinned_layers = partition
                    body = ", ".join(scroll_widgets) or "const SizedBox.shrink()"
                else:
                    body = ", ".join(stack_children) or "const SizedBox.shrink()"
            else:
                body = ", ".join(stack_children) or "const SizedBox.shrink()"
        else:
            body = ", ".join(stack_children) or "const SizedBox.shrink()"
        stack_clip = (
            "Clip.none" if not is_layout_root or stack_needs_soft_clip(node) else "Clip.hardEdge"
        )
        stack_widget = f"Stack(clipBehavior: {stack_clip}, children: [{body}])"
        if viewport_pinned_layers is not None:
            full_body = ", ".join(stack_children) or "const SizedBox.shrink()"
            preview_stack_widget = f"Stack(clipBehavior: {stack_clip}, children: [{full_body}])"
    if interaction == "button":
        from figma_flutter_agent.generator.layout.flex_policy.buttons import (
            bottom_nav_active_tab_icon_band_height,
            bottom_nav_active_tab_should_split_surface_label,
            vertical_chip_button_should_paint_icon_surface_only,
            vertical_chip_icon_surface_height,
        )
        from figma_flutter_agent.parser.interaction import button_hosts_multiple_auth_rows

        if button_hosts_multiple_auth_rows(node):
            pass
        elif vertical_chip_button_should_paint_icon_surface_only(
            node
        ) or bottom_nav_active_tab_should_split_surface_label(node):
            icon_widgets: list[str] = []
            button_label_widgets: list[str] = []
            widget_iter = iter(child_widgets)
            for child in sorted_children:
                if (
                    child.id in paired_circle_ids
                    or child.id in omit_child_ids
                    or child.id in playback_seek_ids
                    or child.id in playback_decor_omit_ids
                ):
                    continue
                try:
                    widget = next(widget_iter)
                except StopIteration:
                    break
                if child.type == NodeType.TEXT:
                    button_label_widgets.append(widget)
                else:
                    icon_widgets.append(widget)
            icon_body = ", ".join(icon_widgets) or "const SizedBox.shrink()"
            icon_stack = f"Stack(clipBehavior: Clip.none, children: [{icon_body}])"
            if bottom_nav_active_tab_should_split_surface_label(node):
                band_height = bottom_nav_active_tab_icon_band_height(node)
            else:
                band_height = vertical_chip_icon_surface_height(node)
            icon_stack = _wrap_button_stack(
                icon_stack,
                node,
                theme_variant=theme_variant,
                band_height=band_height,
            )
            width_lit = format_geometry_literal(float(node.sizing.width or 65.0))
            height_lit = format_geometry_literal(band_height)
            label_body = ", ".join(button_label_widgets)
            stack_widget = (
                "Stack(clipBehavior: Clip.none, children: ["
                f"Positioned(left: 0.0, top: 0.0, width: {width_lit}, height: {height_lit}, "
                f"child: {icon_stack})"
                f"{', ' if label_body else ''}{label_body}"
                "])"
            )
        elif len(child_widgets) == 1 and "InkWell(" in child_widgets[0]:
            stack_widget = child_widgets[0]
        else:
            stack_widget = _wrap_button_stack(stack_widget, node, theme_variant=theme_variant)
    from figma_flutter_agent.generator.layout.widgets.hero import (
        hero_card_clip_radius,
        layout_fact_hero_editorial_cover_stack,
    )

    if layout_fact_hero_editorial_cover_stack(node):
        clip_radius = hero_card_clip_radius(node)
        if clip_radius is not None and clip_radius > 0:
            radius_lit = format_geometry_literal(clip_radius)
            stack_widget = f"ClipRRect(borderRadius: BorderRadius.circular({radius_lit}), child: {stack_widget})"
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_should_emit_surface_decoration,
    )
    from figma_flutter_agent.generator.layout.scroll import wrap_flex_auto_layout_padding

    root_decoration = (
        box_decoration_expr(
            node.style,
            width=node.sizing.width,
            height=node.sizing.height,
        )
        if stack_should_emit_surface_decoration(node, is_layout_root=is_layout_root)
        else None
    )
    if root_decoration is not None:
        stack_widget = wrap_flex_auto_layout_padding(node, stack_widget)
        if node.style.clips_content and (node.style.border_radius or 0) > 0:
            radius_lit = format_geometry_literal(float(node.style.border_radius))
            stack_widget = (
                f"ClipRRect(borderRadius: BorderRadius.circular({radius_lit}), "
                f"child: {stack_widget})"
            )
        stack_widget = f"Container(decoration: {root_decoration}, child: {stack_widget})"
    stack_widget = _wrap_root_stack_viewport(
        node,
        stack_widget,
        is_layout_root=is_layout_root,
        responsive_enabled=responsive_enabled,
        theme_variant=theme_variant,
        viewport_pinned_layers=viewport_pinned_layers,
        preview_stack_widget=preview_stack_widget,
    )
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_stack_overflowing_horizontal_content_strip,
    )
    from figma_flutter_agent.generator.layout.scroll import (
        wrap_horizontal_intrinsic_content_scroll,
    )

    if layout_fact_stack_overflowing_horizontal_content_strip(
        node,
        parent_node=parent_node,
    ):
        stack_widget = wrap_horizontal_intrinsic_content_scroll(
            stack_widget,
            height=node.sizing.height,
        )
    return _finalize_widget(
        node,
        stack_widget,
        parent_type=parent_type,
        parent_node=parent_node,
        scroll_content_root=scroll_content_root,
    )
