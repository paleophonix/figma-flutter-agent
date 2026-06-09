"""Main per-node widget expression emitter: render_node_body."""

from __future__ import annotations

import math
from collections.abc import Callable

from figma_flutter_agent.generator.cluster_variants import ClusterVectorVariant
from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.emit_text_span import (
    emit_text_rich,
    emit_text_span_children_from_node,
)
from figma_flutter_agent.generator.figma_anchor import figma_value_key_arg
from figma_flutter_agent.generator.geometry.affine import (
    matrix4_close_suffix,
    matrix4_compose_expr,
    requires_raster_tier,
)
from figma_flutter_agent.generator.layout.common import (
    escape_dart_string,
    normalize_box_constraints,
    wrap_repaint_boundary,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_back_nav_stack as cupertino_wrap_back_nav_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_button_stack as cupertino_wrap_button_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_circular_button_stack as cupertino_wrap_circular_button_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_scroll_viewport,
)
from figma_flutter_agent.generator.layout.form import (
    render_button,
    render_checkbox,
    render_dialog,
    render_dropdown,
    render_input,
    render_radio,
    render_radio_group,
    render_slider,
    render_switch,
    wrap_material_input_child,
)
from figma_flutter_agent.generator.layout.navigation.bottom import render_bottom_navigation
from figma_flutter_agent.generator.layout.navigation.tabs import (
    render_carousel,
    render_tabs,
)
from figma_flutter_agent.generator.layout.responsive import (
    should_apply_responsive_column_reflow,
    wrap_responsive_root_column,
)
from figma_flutter_agent.generator.layout.scroll import (
    render_both_axis_scroll,
    render_grid_view,
    render_scroll_list,
    scroll_axis_for_list,
    wrap_flex_auto_layout_padding,
)
from figma_flutter_agent.generator.layout.style import (
    border_radius_expr,
    box_decoration_expr,
    box_foreground_decoration_expr,
    card_elevation_expr,
    dart_color_expr,
    has_box_decoration,
    is_dark_fill_color,
    should_emit_strut_style,
    strut_style_expr,
    text_align_expr,
    text_style_expr,
    text_widget_trailing_params,
    wrap_tight_chip_label,
)
from figma_flutter_agent.generator.layout.style.decoration import _shadow_expr
from figma_flutter_agent.generator.render_units import (
    format_figma_blur_sigma_literal,
    snap_to_device_pixel,
)
from figma_flutter_agent.generator.variant.state import variant_blocks_interaction
from figma_flutter_agent.parser.interaction import (
    _BACK_NAV_DESCENDANT_DEPTH,
    _descendant_nodes,
    _has_circular_container,
    _is_footer_link_text_node,
    _label_matches_action_hint,
    _local_nodes,
    _stack_spans_primary_button_and_footer_link,
    button_stack_has_left_icon,
    input_children_are_presentational,
    input_flex_value_text,
    input_hint_node,
    input_value_style_node,
    input_hint_text,
    input_surface_node,
    input_trailing_chrome_nodes,
    interaction_surface_node,
    is_back_navigation_icon_stack,
    is_link_text,
    looks_like_back_nav_stack,
    looks_like_bottom_docked_sheet,
    looks_like_checkbox_control,
    looks_like_compact_icon_action_button,
    looks_like_compact_icon_action_stack,
    looks_like_favorite_icon_button,
    looks_like_password_field_stack,
    looks_like_plus_icon_button,
    looks_like_stroke_minus_icon,
    looks_like_stroke_plus_icon,
    looks_like_play_pause_control_stack,
    looks_like_skip_control_stack,
    looks_like_textarea_field,
    primary_surface_node,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
    round_geometry,
)
from figma_flutter_agent.parser.render_bounds import (
    child_has_outward_paint,
    stack_needs_soft_clip,
)
from figma_flutter_agent.parser.stack_paint import (
    sort_absolute_stack_children as _sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import (
    AxisPins,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    SizingMode,
    StackPlacement,
    WrapKind,
)

from .shared import _node_layout_size, figma_positioned_dimensions, snap_device_pixels_scope
from .button import (
    _try_render_checkbox_label_row,
    _try_render_cta_footer_split_stack,
    _try_render_consent_checkbox_row,
    _wrap_button_stack,
    _wrap_link_text,
)
from .decoration import (
    _decorate_widget_with_box_decoration,
    _drop_shadow_exprs,
    _render_stroke_glyph_fallback,
    _wrap_content_layer_blur,
    _wrap_frosted_layer_blur,
    _wrap_widget_with_box_decoration,
)
from .finalize import _finalize_widget, _wrap_accessibility, _wrap_render_boundary_tap
from .input import (
    _find_icon_glyph_expr,
    _find_trailing_input_icon_expr,
    _flex_input_content_padding,
    _input_content_padding,
    _input_text_style_expr,
    _planner_input_content_padding,
    _render_flex_input_with_trailing_chrome,
    _render_input_trailing_suffix_icon,
    _render_stack_input,
    _render_textarea_field,
    _stack_input_decoration,
)
from .layout import (
    _apply_layout_slot_wraps,
    _button_list_tile_row_body,
    _extract_balanced_prefix_child,
    _flex_parent_data_wrapper,
    _flex_spacing_field,
    _hoist_flex_parent_data,
    _is_stretched_width_box,
    _positioned_fields,
    _positioned_fields_from_pins,
    _resolved_bottom_offset,
    _should_pin_bottom,
    _stack_has_bottom_anchored_child,
    _unwrap_flex_parent_data_wrapper,
    _wrap_center_preserving_flex_parent_data,
    _wrap_sizing,
)
from .photo import (
    try_render_cart_thumbnail_button,
    try_render_oversized_photo_clip_column,
    try_render_space_between_text_metric_row,
    try_render_square_product_photo_stack,
)
from .playback import (
    _find_concentric_circle_pair,
    _playback_seek_omit_child_ids,
    _playback_seek_vector_ids,
    _render_concentric_circle_thumb,
    _render_native_blur_vector,
    _render_playback_seek_slider,
    _render_svg_picture_variant,
    _render_synthetic_play_pause_control,
    _should_suppress_playback_slider_node,
    _sizing_like_skip_control,
    _try_render_play_pause_stack,
    _try_render_pruned_cluster_skip_control,
)
from .position import (
    _child_needs_positioned_bounds,
    _ensure_positioned_stack_bounds,
    _node_has_nested_stack,
    _positioned_horizontal_box_fields,
    _render_leaf_surface,
    _wrap_root_column_viewport,
    _wrap_root_stack_viewport,
)
from .svg import (
    _apply_node_transform,
    _clamp_centered_text_to_parent_stack,
    _is_composite_icon_stack,
    _is_roughly_square,
    _is_skip_control_stack,
    _render_exported_vector,
    _render_svg_picture,
    _should_center_in_parent_stack,
    _should_prefer_exported_svg,
    _skip_control_numeral_top,
    _wrap_centered_stack_child,
)
from .text import (
    _apply_stack_position,
    _ensure_text_center_align,
    _position_button_stack_label,
    _render_explicit_multiline_text_lines,
    _should_center_text_in_button_stack,
    _wrap_bounded_positioned_slot_child,
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
    return (
        width is not None and height is not None and width <= 220.0 and height <= 48.0
    )


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
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str,
    cluster_classes: dict[str, str] | None,
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None,
    cluster_vector_variant: ClusterVectorVariant | None,
    skip_cluster_id: str | None,
    responsive_enabled: bool,
    design_artboard_width: float | None = None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    width, height = _logo_wordmark_stack_size(node)
    child_widgets = [
        render_node_body(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
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


def render_node_body(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    parent_type: NodeType | None = None,
    parent_node: CleanDesignTreeNode | None = None,
    theme_variant: str = "material_3",
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None = None,
    cluster_vector_variant: ClusterVectorVariant | None = None,
    skip_cluster_id: str | None = None,
    responsive_enabled: bool = False,
    is_layout_root: bool = False,
    design_artboard_width: float | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    de_archetype_pass: bool = False,
    scroll_content_root: bool = False,
) -> str:
    """Render a Dart widget expression for a clean-tree node."""
    if not de_archetype_pass and _is_logo_wordmark_stack(node):
        return _finalize_widget(
            node,
            _render_logo_wordmark_stack(
                node,
                uses_svg=uses_svg,
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
            ),
            parent_type=parent_type,
        scroll_content_root=scroll_content_root,
        )

    if not de_archetype_pass:
        consent_row = _try_render_consent_checkbox_row(
            node,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if consent_row is not None:
            return _finalize_widget(node, consent_row, parent_type=parent_type, scroll_content_root=scroll_content_root)

    if looks_like_textarea_field(node):
        return _render_textarea_field(
            node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )

    if node.type == NodeType.STACK:
        play_pause_early = (
            None if de_archetype_pass else _try_render_play_pause_stack(node)
        )
        if play_pause_early is not None:
            label = escape_dart_string(node.accessibility_label or node.name)
            play_pause_early = _wrap_button_stack(
                play_pause_early,
                node,
                theme_variant=theme_variant,
            )
            play_pause_early = f"Semantics(label: '{label}', child: {play_pause_early})"
            return _finalize_widget(node, play_pause_early, parent_type=parent_type, scroll_content_root=scroll_content_root)
        photo_stack_early = try_render_square_product_photo_stack(
            node,
            parent_node=parent_node,
            uses_svg=uses_svg,
            render_node_body=render_node_body,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if photo_stack_early is not None:
            return _finalize_widget(
                node,
                photo_stack_early,
                parent_type=parent_type,
                parent_node=parent_node,
                scroll_content_root=scroll_content_root,
            )

    if node.render_boundary and node.vector_asset_key:
        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is not None:
            fill_parent = _should_center_in_parent_stack(node, parent_node)
            widget = _wrap_render_boundary_tap(node, exported)
            if fill_parent:
                widget = _wrap_centered_stack_child(node, widget)
            return _finalize_widget(
                node,
                widget,
                parent_type=parent_type,
                fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
            )

    if node.extracted_widget_ref:
        ref_name = node.extracted_widget_ref.strip()
        widget_expr = f"const {ref_name}()" if ref_name else "const SizedBox.shrink()"
        return _finalize_widget(
            node,
            widget_expr,
            parent_type=parent_type,
        scroll_content_root=scroll_content_root,
        )

    cluster_id = node.cluster_id
    from figma_flutter_agent.parser.interaction import list_tile_leading_icon_slot

    if list_tile_leading_icon_slot(
        node, parent_node, parent_type=parent_type
    ):
        icon_asset = node.vector_asset_key
        if icon_asset is None and cluster_id and cluster_vector_variants:
            variant = cluster_vector_variants.get(cluster_id)
            if variant is not None:
                icon_asset = variant.forward_asset
        width = node.sizing.width or 48.0
        height = node.sizing.height or 48.0
        background = node.style.background_color or "0xFFF6F6F2"
        radius = node.style.border_radius or 18.0
        if icon_asset is not None and uses_svg:
            glyph = _render_svg_picture(node, escape_dart_string(icon_asset))
        elif node.type == NodeType.BUTTON and looks_like_compact_icon_action_button(node):
            glyph = _find_icon_glyph_expr(node) or "const SizedBox.shrink()"
        elif parent_node is not None and len(parent_node.children) > 1:
            from figma_flutter_agent.generator.layout.navigation.items import nav_icon_expr

            title_host = parent_node.children[1]
            glyph = nav_icon_expr(title_host, uses_svg=False)
        else:
            glyph = "const SizedBox.shrink()"
        widget = (
            f"Container(width: {format_geometry_literal(width)}, "
            f"height: {format_geometry_literal(height)}, "
            f"decoration: BoxDecoration(color: Color({background}), "
            f"borderRadius: BorderRadius.circular({format_geometry_literal(radius)})), "
            "child: Row(mainAxisAlignment: MainAxisAlignment.center, "
            f"crossAxisAlignment: CrossAxisAlignment.center, children: [{glyph}]))"
        )
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            parent_node=parent_node,
            scroll_content_root=scroll_content_root,
        )

    pruned_cluster_has_instance_asset = (
        cluster_id is not None
        and not node.children
        and bool(node.flatten_figma_node_ids)
        and bool(node.vector_asset_key)
    )
    from figma_flutter_agent.generator.layout.flex_policy import (
        row_is_numeric_counter_badge,
        row_is_status_pill_badge,
        row_is_tight_horizontal_pill_label,
    )
    from figma_flutter_agent.parser.interaction import hosts_compact_checkbox_control

    inline_cluster_control = (
        row_is_tight_horizontal_pill_label(node)
        or row_is_status_pill_badge(node)
        or row_is_numeric_counter_badge(node)
        or hosts_compact_checkbox_control(node)
        or (
            node.type == NodeType.BUTTON
            and looks_like_compact_icon_action_button(node)
            and not (
                cluster_id
                and cluster_classes
                and cluster_id in cluster_classes
            )
        )
    )
    prefer_cluster_widget = (
        not inline_cluster_control
        and cluster_classes
        and cluster_id
        and cluster_id in cluster_classes
        and cluster_id != skip_cluster_id
        and not (
            pruned_cluster_has_instance_asset
            and cluster_id not in cluster_classes
        )
    )
    if prefer_cluster_widget:
        from figma_flutter_agent.generator.cluster_variants import (
            cluster_reference_args,
        )

        class_name = cluster_classes[cluster_id]
        variant = (
            cluster_vector_variants.get(cluster_id) if cluster_vector_variants else None
        )
        if variant is not None and _sizing_like_skip_control(node):
            args = cluster_reference_args(node, variant)
            widget_expr = (
                f"const {class_name}({args})" if args else f"const {class_name}()"
            )
            label = escape_dart_string(
                node.accessibility_label or node.name or class_name
            )
            return _finalize_widget(
                node,
                f"Semantics(label: '{label}', child: {widget_expr})",
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )
        if variant is not None:
            args = cluster_reference_args(node, variant)
            if args:
                return _finalize_widget(
                    node,
                    f"{class_name}({args})",
                    parent_type=parent_type,
                scroll_content_root=scroll_content_root,
                )
        return _finalize_widget(node, f"const {class_name}()", parent_type=parent_type, scroll_content_root=scroll_content_root)

    if (
        not de_archetype_pass
        and node.type == NodeType.STACK
        and not node.children
        and _sizing_like_skip_control(node)
    ):
        variant = (
            cluster_vector_variants.get(node.cluster_id)
            if cluster_vector_variants and node.cluster_id
            else None
        )
        pruned = _try_render_pruned_cluster_skip_control(
            node,
            uses_svg=uses_svg,
            skip_cluster_id=skip_cluster_id,
            cluster_vector_variant=variant,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if pruned is not None:
            label = escape_dart_string(node.accessibility_label or node.name)
            return _finalize_widget(
                node,
                f"Semantics(label: '{label}', child: {pruned})",
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )

    if node.type == NodeType.STACK and not is_layout_root:
        from figma_flutter_agent.generator.layout.interactive import (
            render_time_wheel_picker_stack,
            render_weekday_chip_row,
        )
        from figma_flutter_agent.parser.interaction import (
            WEEKDAY_CHIP_ROW_NAME,
            looks_like_wheel_time_picker_stack,
        )

        if node.name == WEEKDAY_CHIP_ROW_NAME:
            return _finalize_widget(
                node,
                render_weekday_chip_row(node),
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )
        if looks_like_wheel_time_picker_stack(node):
            return _finalize_widget(
                node,
                render_time_wheel_picker_stack(node),
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )
        cta_footer_split = (
            None
            if de_archetype_pass
            else _try_render_cta_footer_split_stack(
                node,
                uses_svg=uses_svg,
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
            )
        )
        if cta_footer_split is not None:
            return _finalize_widget(node, cta_footer_split, parent_type=parent_type, scroll_content_root=scroll_content_root)

    sorted_children = _sort_absolute_stack_children(
        node.children,
        is_layout_root=is_layout_root,
    )
    from figma_flutter_agent.generator.layout.flex_policy import (
        stack_child_ordinal_top,
        stack_is_card_metadata_host,
    )

    metadata_column_host = (
        not is_layout_root
        and node.type == NodeType.STACK
        and stack_is_card_metadata_host(node, parent_node=parent_node)
    )
    if metadata_column_host:
        sorted_children = sorted(
            sorted_children,
            key=lambda child: (stack_child_ordinal_top(child), child.id),
        )
    paired_circle_ids: set[str] = set()
    merged_thumb_widgets: list[str] = []
    omit_child_ids: set[str] = set()
    playback_seek_ids: set[str] = set()
    playback_decor_omit_ids: set[str] = set()
    if node.type == NodeType.STACK:
        playback_seek_ids = _playback_seek_vector_ids(node)
        if playback_seek_ids:
            playback_decor_omit_ids = _playback_seek_omit_child_ids(node)
    if node.type == NodeType.STACK:
        circle_pair = (
            _find_concentric_circle_pair(sorted_children)
            if not playback_seek_ids
            else None
        )
        if circle_pair is not None:
            outer, inner = circle_pair
            paired_circle_ids = {outer.id, inner.id}
            merged_thumb_widgets = _render_concentric_circle_thumb(
                outer,
                inner,
                stack_siblings=sorted_children,
            )
        if not is_layout_root and stack_interaction_kind(node) == "button":
            surface = primary_surface_node(node)
            if surface is not None:
                omit_child_ids.add(surface.id)
    if node.type == NodeType.BUTTON:
        surface = primary_surface_node(node)
        if surface is not None:
            omit_child_ids.add(surface.id)

    child_widgets = [
        render_node_body(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.COLUMN if metadata_column_host else node.type,
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
        )
        for child in sorted_children
        if child.id not in paired_circle_ids
        and child.id not in omit_child_ids
        and child.id not in playback_seek_ids
        and child.id not in playback_decor_omit_ids
    ]
    if merged_thumb_widgets:
        child_widgets.extend(merged_thumb_widgets)
    playback_seek_widget: str | None = None
    if playback_seek_ids:
        playback_seek_widget = _render_playback_seek_slider(node)
    from figma_flutter_agent.generator.layout.flex_policy import (
        resolve_cross_axis_alignment,
        resolve_main_axis_alignment,
    )

    main_axis = resolve_main_axis_alignment(
        node,
        scroll_content_root=scroll_content_root,
    )

    cross_axis = resolve_cross_axis_alignment(
        node,
        parent_type=parent_type,
        cross=node.alignment.cross,
    )

    if node.type == NodeType.TEXT:
        from figma_flutter_agent.generator.layout.flex_policy import (
            text_in_card_metadata_rail,
            text_host_is_tight_positioned,
            row_is_status_pill_badge,
        )

        align = text_align_expr(node.style)
        align_suffix = f", textAlign: {align}" if align else ""
        metadata_rail = text_in_card_metadata_rail(
            node,
            parent_node,
            parent_type=parent_type,
        )
        from figma_flutter_agent.generator.layout.common import (
            is_centered_glyph_badge,
            is_short_centered_glyph_text,
        )

        centered_glyph_parent = (
            parent_node is not None and is_centered_glyph_badge(parent_node)
        )
        from figma_flutter_agent.generator.layout.flex_policy import (
            button_is_pill_with_centered_label,
        )

        omit_glyph_strut = (
            centered_glyph_parent
            or is_short_centered_glyph_text(node)
            or (
                text_host_is_tight_positioned(node)
                and not should_emit_strut_style(node.style)
            )
            or (
                parent_node is not None
                and parent_type in {NodeType.ROW, NodeType.COLUMN}
                and row_is_status_pill_badge(parent_node)
            )
            or (
                parent_node is not None
                and parent_type == NodeType.BUTTON
                and button_is_pill_with_centered_label(parent_node)
            )
        )
        strut = (
            None
            if omit_glyph_strut
            else strut_style_expr(node.style, omit_leading=metadata_rail)
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
            text = escape_dart_string(node.text or node.name)
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
                from figma_flutter_agent.generator.layout.flex_policy import (
                    row_is_tight_horizontal_pill_label,
                )

                text = escape_dart_string(node.text or node.name)
                pill_label = (
                    parent_node is not None
                    and parent_type == NodeType.ROW
                    and row_is_tight_horizontal_pill_label(parent_node)
                )
                trailing = text_widget_trailing_params(
                    node.style,
                    text_align_suffix=align_suffix,
                    omit_strut=omit_glyph_strut,
                    optical_center=omit_glyph_strut
                    and (node.style.text_align or "").upper() == "CENTER",
                )
                widget = f"Text('{text}', style: {style_expr}, {trailing})"
                if pill_label:
                    widget = wrap_tight_chip_label(widget)
                elif metadata_rail:
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
        elif (
            (node.style.text_align or "").upper() == "CENTER"
            and parent_type == NodeType.COLUMN
        ):
            widget = (
                "SizedBox(width: double.infinity, child: "
                f"Center(child: {widget}))"
            )
        text_width = node.sizing.width
        if (
            "\n" in (node.text or "")
            and text_width is not None
            and text_width > 0
            and node.sizing.width_mode != SizingMode.FILL
            and (node.style.text_align or "").upper() != "CENTER"
        ):
            widget = (
                f"SizedBox(width: {format_geometry_literal(text_width)}, child: {widget})"
            )
        if is_link_text(node.text):
            widget = _wrap_link_text(widget)
        if (
            parent_node is not None
            and parent_type in {NodeType.STACK, NodeType.BUTTON}
            and node.stack_placement is not None
            and _should_center_text_in_button_stack(parent_node, node)
        ):
            widget = _wrap_accessibility(node, widget)
            return _position_button_stack_label(
                widget,
                text_node=node,
                parent_node=parent_node,
                placement=node.stack_placement,
            )
        if parent_node is not None and _is_skip_control_stack(parent_node):
            placement = node.stack_placement
            style_expr = text_style_expr(
                node,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
            text = escape_dart_string(node.text or node.name)
            trailing = text_widget_trailing_params(
                node.style,
                text_align_suffix=", textAlign: TextAlign.center",
            )
            widget = f"Text('{text}', style: {style_expr}, {trailing})"
            widget = _wrap_accessibility(node, f"Center(child: {widget})")
            if placement is not None and parent_type == NodeType.STACK:
                fields = _positioned_fields(placement)
                _ensure_positioned_stack_bounds(fields, node, placement)
                numeral_top = _skip_control_numeral_top(parent_node, node, placement)
                fields = [
                    field if not field.startswith("top:") else f"top: {numeral_top}"
                    for field in fields
                ]
                return f"Positioned({', '.join(fields)}, child: {widget})"
            return widget
        node = _clamp_centered_text_to_parent_stack(node, parent_node)
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

    if node.type in {NodeType.IMAGE, NodeType.VECTOR} and node.vector_asset_key:
        raw_asset = node.vector_asset_key
        if cluster_vector_variant and raw_asset in {
            cluster_vector_variant.forward_asset,
            cluster_vector_variant.backward_asset,
        }:
            widget = _render_svg_picture_variant(
                node,
                forward_asset=cluster_vector_variant.forward_asset,
                backward_asset=cluster_vector_variant.backward_asset,
                param_name=cluster_vector_variant.param_name,
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

        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is not None:
            widget = exported
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

    if node.type in {NodeType.IMAGE, NodeType.VECTOR} and (
        node.style.layer_blur or node.vector_svg_has_filter
    ):
        widget = _render_native_blur_vector(node)
        fill_parent = _should_center_in_parent_stack(node, parent_node)
        if fill_parent:
            widget = _wrap_centered_stack_child(node, widget)
        return _finalize_widget(
            node,
            widget,
            parent_type=parent_type,
            fill_parent=fill_parent,
        scroll_content_root=scroll_content_root,
        )

    if node.image_asset_key and not node.children:
        exported = _render_exported_vector(node, uses_svg=uses_svg)
        if exported is not None:
            fill_parent = _should_center_in_parent_stack(node, parent_node)
            widget = exported
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

    if node.type == NodeType.CHECKBOX:
        widget = render_checkbox(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.SWITCH:
        widget = render_switch(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.RADIO_GROUP:
        widget = render_radio_group(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.RADIO:
        widget = render_radio(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.DROPDOWN:
        widget = render_dropdown(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.DIALOG:
        widget = render_dialog(
            node, child_widgets=child_widgets, theme_variant=theme_variant
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.SLIDER:
        if _should_suppress_playback_slider_node(node, parent_node):
            return _finalize_widget(
                node,
                "const SizedBox.shrink()",
                parent_type=parent_type,
            scroll_content_root=scroll_content_root,
            )
        widget = render_slider(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.BUTTON:
        cart_thumbnail = try_render_cart_thumbnail_button(
            node,
            uses_svg=uses_svg,
            render_node_body=render_node_body,
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
        )
        if is_compact_icon_button:
            glyph = _find_icon_glyph_expr(node)
            if looks_like_stroke_plus_icon(node) or looks_like_stroke_minus_icon(node):
                tap_role = "button-action"
            elif looks_like_plus_icon_button(node) or looks_like_favorite_icon_button(node):
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
            from figma_flutter_agent.parser.interaction import (
                button_has_composite_row_body,
                button_has_list_tile_row_body,
            )

            if button_has_list_tile_row_body(node):
                stack_body = _button_list_tile_row_body(node, child_widgets)
            else:
                from figma_flutter_agent.generator.layout.flex_policy import (
                    button_hosts_status_pill,
                    button_should_fitted_box_label,
                    horizontal_chip_button_should_hug_width,
                )

                if (
                    len(child_widgets) == 1
                    and len(node.children) == 1
                    and node.children[0].type == NodeType.TEXT
                ):
                    body = child_widgets[0]
                    if button_should_fitted_box_label(node):
                        body = (
                            "FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.center, "
                            f"child: {body})"
                        )
                    body = _wrap_center_preserving_flex_parent_data(body)
                else:
                    body = ", ".join(child_widgets)
                stack_fit = (
                    "StackFit.loose"
                    if button_has_composite_row_body(node)
                    or horizontal_chip_button_should_hug_width(node)
                    or button_hosts_status_pill(node)
                    else "StackFit.expand"
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
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.INPUT:
        if looks_like_checkbox_control(node):
            widget = render_checkbox(node, theme_variant=theme_variant)
            width = node.sizing.width
            height = node.sizing.height
            if width is not None and height is not None and width > 0 and height > 0:
                widget = f"SizedBox(width: {width}, height: {height}, child: {widget})"
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        trailing = input_trailing_chrome_nodes(node)
        if input_flex_value_text(node) and trailing:
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
        if child_widgets and input_children_are_presentational(node):
            if trailing:
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
            )
        if child_widgets:
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            widget = f"Column(crossAxisAlignment: {cross_axis}, children: [{body}])"
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        widget = render_input(node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.CONTAINER and looks_like_checkbox_control(node):
        widget = render_checkbox(node, theme_variant=theme_variant)
        width = node.sizing.width
        height = node.sizing.height
        if width is not None and height is not None and width > 0 and height > 0:
            widget = f"SizedBox(width: {width}, height: {height}, child: {widget})"
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.CARD:
        from figma_flutter_agent.generator.layout.flex_policy import (
            card_has_edge_to_edge_hero_stack,
        )

        elevation = card_elevation_expr(node.style)
        radius = border_radius_expr(node.style)
        if card_has_edge_to_edge_hero_stack(node) and len(child_widgets) >= 2:
            hero_widget = child_widgets[0]
            meta_body = ", ".join(child_widgets[1:]) or "const SizedBox.shrink()"
            card_height = node.sizing.height
            hero_height = node.children[0].sizing.height
            height_lit = (
                format_geometry_literal(float(card_height))
                if card_height is not None and card_height > 0
                else None
            )
            hero_lit = (
                format_geometry_literal(float(hero_height))
                if hero_height is not None and hero_height > 0
                else None
            )
            if height_lit is not None and hero_lit is not None:
                widget = (
                    f"Material("
                    f"elevation: {elevation}, "
                    f"borderRadius: {radius}, "
                    "clipBehavior: Clip.antiAlias, "
                    f"child: SizedBox("
                    f"height: {height_lit}, "
                    "child: Column("
                    "mainAxisSize: MainAxisSize.max, "
                    f"crossAxisAlignment: {cross_axis}, "
                    f"children: [SizedBox(height: {hero_lit}, child: {hero_widget}), "
                    f"Expanded(child: {meta_body})]"
                    ")))"
                )
            else:
                widget = (
                    f"Material("
                    f"elevation: {elevation}, "
                    f"borderRadius: {radius}, "
                    "clipBehavior: Clip.antiAlias, "
                    f"child: Column("
                    "mainAxisSize: MainAxisSize.min, "
                    f"crossAxisAlignment: {cross_axis}, "
                    f"children: [{hero_widget}, {meta_body}]"
                    "))"
                )
        else:
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            widget = (
                f"Card("
                f"elevation: {elevation}, "
                f"shape: RoundedRectangleBorder(borderRadius: {radius}), "
                f"child: Padding("
                f"padding: const EdgeInsets.all(AppSpacing.md), "
                f"child: Column(crossAxisAlignment: {cross_axis}, children: [{body}])"
                f")"
                f")"
            )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.TABS:
        widget = render_tabs(child_widgets, node, theme_variant=theme_variant)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.CAROUSEL:
        widget = render_carousel(child_widgets, node, parent_type=parent_type)
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.BOTTOM_NAV:
        from figma_flutter_agent.generator.layout.navigation.host import (
            compose_bottom_navigation_host,
        )

        widget = compose_bottom_navigation_host(
            node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.WRAP:
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        spacing = format_geometry_literal(node.spacing)
        widget = f"Wrap(spacing: {spacing}, runSpacing: {spacing}, children: [{body}])"
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.GRID:
        widget = render_grid_view(
            node,
            child_widgets,
            parent_type=parent_type,
            responsive_enabled=responsive_enabled,
            is_layout_root=is_layout_root,
            design_artboard_width=design_artboard_width,
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.ROW:
        if node.scroll_axis == "horizontal":
            widget = render_scroll_list(
                node,
                child_widgets,
                axis="horizontal",
                parent_type=parent_type,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        from figma_flutter_agent.generator.layout.common import is_centered_glyph_badge
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
        metric_row = try_render_space_between_text_metric_row(
            node,
            child_widgets=child_widgets,
            uses_svg=uses_svg,
            render_node_body=render_node_body,
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
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if is_centered_glyph_badge(node) and len(node.children) == 1:
            text_body = render_node_body(
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
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
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
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if row_is_status_pill_badge(node) and child_widgets:
            if len(child_widgets) == 1:
                pad_lr = 8.0
                if node.padding is not None:
                    pad_lr = max(
                        float(node.padding.left or 0.0),
                        float(node.padding.right or 0.0),
                        pad_lr,
                    )
                body = (
                    "Padding("
                    "padding: "
                    f"const EdgeInsets.symmetric(horizontal: {format_geometry_literal(pad_lr)}), "
                    "child: Row("
                    "mainAxisSize: MainAxisSize.min, "
                    "mainAxisAlignment: MainAxisAlignment.center, "
                    "crossAxisAlignment: CrossAxisAlignment.center, "
                    f"children: [{child_widgets[0]}]))"
                )
            else:
                spacing_field = _flex_spacing_field(node)
                body = (
                    f"Row(mainAxisAlignment: {main_axis}, "
                    f"crossAxisAlignment: {cross_axis}, "
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
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if uses_svg and _should_prefer_exported_svg(node):
            exported = _render_exported_vector(node, uses_svg=uses_svg)
            if exported is not None:
                width = node.sizing.width
                height = node.sizing.height
                if (
                    width is not None
                    and height is not None
                    and width > 0
                    and height > 0
                ):
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
                    node, widget, parent_type=parent_type, parent_node=parent_node
                , scroll_content_root=scroll_content_root)
        from figma_flutter_agent.generator.layout.flex_policy import (
            row_equal_metric_cards_cross_axis,
            wrap_equal_metric_cards_row_height,
        )

        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
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
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.COLUMN:
        from figma_flutter_agent.generator.layout.flex_policy import (
            row_is_status_pill_badge,
        )

        if row_is_status_pill_badge(node) and child_widgets:
            if len(child_widgets) == 1:
                pad_lr = 8.0
                if node.padding is not None:
                    pad_lr = max(
                        float(node.padding.left or 0.0),
                        float(node.padding.right or 0.0),
                        pad_lr,
                    )
                body = (
                    "Padding("
                    "padding: "
                    f"const EdgeInsets.symmetric(horizontal: {format_geometry_literal(pad_lr)}), "
                    "child: Row("
                    "mainAxisSize: MainAxisSize.min, "
                    "mainAxisAlignment: MainAxisAlignment.center, "
                    "crossAxisAlignment: CrossAxisAlignment.center, "
                    f"children: [{child_widgets[0]}]))"
                )
            else:
                spacing_field = _flex_spacing_field(node)
                body = (
                    f"Row(mainAxisAlignment: {main_axis}, "
                    f"crossAxisAlignment: {cross_axis}, "
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
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
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
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if node.scroll_axis == "both":
            widget = render_both_axis_scroll(
                node,
                child_widgets,
                parent_type=parent_type,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        scroll_axis = scroll_axis_for_list(node)
        if scroll_axis is not None:
            widget = render_scroll_list(
                node,
                child_widgets,
                axis=scroll_axis,
                parent_type=parent_type,
            )
            return _finalize_widget(
                node, widget, parent_type=parent_type, parent_node=parent_node
            , scroll_content_root=scroll_content_root)
        if should_apply_responsive_column_reflow(
            responsive_enabled=responsive_enabled,
            scroll_axis=node.scroll_axis,
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
            body = ", ".join(child_widgets) or "const SizedBox.shrink()"
            from figma_flutter_agent.generator.layout.flex_policy import (
                _column_is_text_primary,
                _column_peer_in_bounded_row,
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
                    child.type == NodeType.TEXT
                    and (child.style.text_align or "LEFT").upper() == "LEFT"
                    for child in node.children
                ):
                    align = "Alignment.centerLeft"
                else:
                    align = column_cross_to_align_expr(cross)
                widget = f"Align(alignment: {align}, child: {body})"
            else:
                spacing_field = _flex_spacing_field(node)
                main_size_field = (
                    "mainAxisSize: MainAxisSize.min, "
                    if scroll_content_root
                    or _column_peer_in_bounded_row(node, parent_node=parent_node)
                    or _column_is_text_primary(node)
                    or column_in_bounded_positioned_host(node)
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
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    if node.type == NodeType.STACK:
        from figma_flutter_agent.assets.composite_icons import (
            is_composite_icon_export_node,
        )

        if uses_svg and is_composite_icon_export_node(node) and node.vector_asset_key:
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
                fill_parent=fill_parent,
            scroll_content_root=scroll_content_root,
            )
        play_pause = _try_render_play_pause_stack(node)
        if play_pause is not None:
            label = escape_dart_string(node.accessibility_label or node.name)
            play_pause = _wrap_button_stack(
                play_pause, node, theme_variant=theme_variant
            )
            play_pause = f"Semantics(label: '{label}', child: {play_pause})"
            return _finalize_widget(node, play_pause, parent_type=parent_type, scroll_content_root=scroll_content_root)
        photo_stack = try_render_square_product_photo_stack(
            node,
            parent_node=parent_node,
            uses_svg=uses_svg,
            render_node_body=render_node_body,
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
            return _finalize_widget(node, pruned_skip, parent_type=parent_type, scroll_content_root=scroll_content_root)
        if not is_layout_root and looks_like_back_nav_stack(node):
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
        if not is_layout_root and looks_like_skip_control_stack(node):
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
        interaction = None if is_layout_root else stack_interaction_kind(node)
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
            stack_should_flow_as_centered_wrap,
            stack_should_flow_as_column,
        )

        if stack_should_flow_as_centered_wrap(node):
            ordered_pairs = sorted(
                zip(sorted_children, stack_children, strict=True),
                key=lambda pair: (
                    stack_child_ordinal_top(pair[0]),
                    stack_child_ordinal_left(pair[0]),
                    pair[0].id,
                ),
            )
            spacing_lit = format_geometry_literal(
                stack_pill_button_wrap_spacing(node.children)
            )
            flow_parts = [widget for _, widget in ordered_pairs]
            body = ", ".join(flow_parts) or "const SizedBox.shrink()"
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
            ordered_pairs = sorted(
                zip(sorted_children, stack_children, strict=True),
                key=lambda pair: (stack_child_ordinal_top(pair[0]), pair[0].id),
            )
            flow_parts: list[str] = []
            for index, (child, widget) in enumerate(ordered_pairs):
                if index > 0:
                    previous_child = ordered_pairs[index - 1][0]
                    gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(
                        previous_child
                    )
                    if gap > 0.5:
                        flow_parts.append(
                            f"SizedBox(height: {format_geometry_literal(gap)})"
                        )
                flow_widget = stack_flow_child_horizontal_wrap(child, widget)
                flow_widget = stack_flow_child_vertical_extent_wrap(child, flow_widget)
                if column_child_should_center_hug(node, child):
                    flow_widget = column_center_hug_child_wrap(node, child, flow_widget)
                flow_parts.append(flow_widget)
            body = ", ".join(flow_parts) or "const SizedBox.shrink()"
            stack_widget = (
                "Column("
                "mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.stretch, "
                f"children: [{body}]"
                ")"
            )
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
                        spacing_field = (
                            f"spacing: {format_geometry_literal(gap)}, "
                        )
            stack_widget = (
                "Column("
                "mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.end, "
                f"{spacing_field}"
                f"children: [{body}]"
                ")"
            )
        else:
            from figma_flutter_agent.generator.layout.stack_chrome import (
                apply_pin_bottom_chrome_to_stack_layers,
            )

            stack_emit_children = [
                child
                for child in sorted_children
                if child.id not in paired_circle_ids
                and child.id not in omit_child_ids
                and child.id not in playback_seek_ids
                and child.id not in playback_decor_omit_ids
            ]
            if len(stack_emit_children) == len(stack_children):
                stack_children = apply_pin_bottom_chrome_to_stack_layers(
                    node,
                    stack_emit_children,
                    stack_children,
                    allow_outward_paint=stack_needs_soft_clip(node),
                )
                body = ", ".join(stack_children) or "const SizedBox.shrink()"
            stack_clip = (
                "Clip.none"
                if not is_layout_root or stack_needs_soft_clip(node)
                else "Clip.hardEdge"
            )
            stack_widget = f"Stack(clipBehavior: {stack_clip}, children: [{body}])"
        if interaction == "button":
            if len(child_widgets) == 1 and "InkWell(" in child_widgets[0]:
                stack_widget = child_widgets[0]
            else:
                stack_widget = _wrap_button_stack(
                    stack_widget, node, theme_variant=theme_variant
                )
        root_decoration = (
            box_decoration_expr(
                node.style,
                width=node.sizing.width,
                height=node.sizing.height,
            )
            if is_layout_root
            else None
        )
        if root_decoration is not None:
            stack_widget = (
                f"Container(decoration: {root_decoration}, child: {stack_widget})"
            )
        stack_widget = _wrap_root_stack_viewport(
            node,
            stack_widget,
            is_layout_root=is_layout_root,
            responsive_enabled=responsive_enabled,
            theme_variant=theme_variant,
        )
        return _finalize_widget(
            node,
            stack_widget,
            parent_type=parent_type,
            parent_node=parent_node,
        scroll_content_root=scroll_content_root,
        )

    if child_widgets:
        body = ", ".join(child_widgets)
        inner = f"Column(crossAxisAlignment: {cross_axis}, children: [{body}])"
        box_decoration = box_decoration_expr(
            node.style,
            width=node.sizing.width,
            height=node.sizing.height,
        )
        if box_decoration is not None and node.type in {
            NodeType.CONTAINER,
            NodeType.COLUMN,
            NodeType.ROW,
        }:
            inner = f"Container(decoration: {box_decoration}, child: {inner})"
        return _finalize_widget(node, inner, parent_type=parent_type, scroll_content_root=scroll_content_root)

    if uses_svg and _should_prefer_exported_svg(node):
        widget = _render_svg_picture(
            node, escape_dart_string(node.vector_asset_key or "")
        )
        return _finalize_widget(
            node, widget, parent_type=parent_type, parent_node=parent_node
        , scroll_content_root=scroll_content_root)

    leaf_surface = _render_leaf_surface(node)
    if leaf_surface is not None:
        return _finalize_widget(node, leaf_surface, parent_type=parent_type, scroll_content_root=scroll_content_root)

    glyph = _render_stroke_glyph_fallback(node)
    if glyph is not None:
        return _finalize_widget(node, glyph, parent_type=parent_type, scroll_content_root=scroll_content_root)

    return _finalize_widget(node, "const SizedBox.shrink()", parent_type=parent_type, scroll_content_root=scroll_content_root)
