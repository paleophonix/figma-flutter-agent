"""Input field and textarea widget emitters."""

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
    looks_like_password_field_stack,
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

from .finalize import _finalize_widget
from .shared import _node_layout_size, figma_positioned_dimensions
from .decoration import (
    _decorate_widget_with_box_decoration,
    _render_stroke_glyph_fallback,
    _wrap_frosted_layer_blur,
    _wrap_widget_with_box_decoration,
)
from .layout import (
    _positioned_fields,
    _positioned_fields_from_pins,
    _resolved_bottom_offset,
    _should_pin_bottom,
    _wrap_sizing,
)
from .position import _ensure_positioned_stack_bounds, _positioned_horizontal_box_fields
from .svg import _render_svg_picture

def _flex_input_content_padding(
    node: CleanDesignTreeNode,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Derive ``InputDecoration.contentPadding`` for flex-hug ``INPUT`` frames."""
    if field_height is None or field_height <= 0:
        return None
    pad = node.padding
    left = pad.left if pad is not None and pad.left is not None else 16.0
    right = pad.right if pad is not None and pad.right is not None else 16.0
    if pad is not None and ((pad.top or 0) > 0 or (pad.bottom or 0) > 0):
        top = pad.top or 0.0
        bottom = pad.bottom or 0.0
        return (
            f"contentPadding: EdgeInsets.fromLTRB(" f"{left}, {top}, {right}, {bottom})"
        )
    value_node = input_value_style_node(node)
    style_ref = value_node or hint_node
    font_size = style_ref.style.font_size if style_ref is not None else 14.0
    text_height = (
        style_ref.style.glyph_height
        if style_ref is not None and style_ref.style.glyph_height
        else font_size
    )
    top = max(0.0, (float(field_height) - float(text_height)) / 2.0)
    bottom = max(0.0, float(field_height) - top - float(text_height))
    return f"contentPadding: EdgeInsets.fromLTRB({left}, {top}, {right}, {bottom})"


def _optical_single_line_input_content_padding(
    node: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Symmetric vertical padding from cap-height centering inside a fixed input."""
    if node is None or field_height is None or field_height <= 0:
        return None
    left = 16.0
    right = 16.0
    if node.padding is not None:
        if node.padding.left is not None:
            left = float(node.padding.left)
        if node.padding.right is not None:
            right = float(node.padding.right)
    value_node = input_value_style_node(node)
    style_ref = value_node or hint_node
    font_size = 14.0
    if style_ref is not None and style_ref.style.font_size is not None:
        font_size = float(style_ref.style.font_size)
    vertical = max(0.0, (float(field_height) - font_size) / 2.0)
    pad = node.padding
    if (
        pad is not None
        and pad.top is not None
        and pad.bottom is not None
        and abs(float(pad.top) - float(pad.bottom)) <= 1.0
    ):
        vertical = max(vertical, float(pad.top))
    left_lit = format_geometry_literal(left)
    right_lit = format_geometry_literal(right)
    top_lit = format_geometry_literal(vertical)
    return f"contentPadding: EdgeInsets.fromLTRB({left_lit}, {top_lit}, {right_lit}, {top_lit})"


def _input_content_padding(
    surface: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Derive ``InputDecoration.contentPadding`` from Figma placeholder placement."""
    if (
        surface is None
        or hint_node is None
        or field_height is None
        or field_height <= 0
    ):
        return None
    placement = hint_node.stack_placement
    if placement is None:
        return None
    left = placement.left if placement.left is not None else 20.0
    text_height = hint_node.style.glyph_height or placement.height
    font_size = hint_node.style.font_size or 16.0
    line_height = hint_node.style.line_height or 1.0
    computed_height = font_size * line_height
    if text_height is None or text_height <= 0:
        text_height = computed_height
    figma_top = (placement.top if placement.top is not None else 0.0) + (
        hint_node.style.glyph_top_offset or 0.0
    )
    centered_top = max(0.0, (field_height - text_height) / 2.0)
    top = figma_top if figma_top >= centered_top - 1.0 else centered_top
    bottom = max(0.0, field_height - top - text_height)
    right = left
    return f"contentPadding: EdgeInsets.fromLTRB({left}, {top}, {right}, {bottom})"


def _planner_input_content_padding(node: CleanDesignTreeNode) -> str | None:
    """Use geometry-planner INPUT padding channel when present."""
    metrics = node.text_metrics_frame
    if metrics is None or metrics.input_padding_top is None:
        return None
    pad = node.padding
    left = pad.left if pad is not None and pad.left is not None else 16.0
    right = pad.right if pad is not None and pad.right is not None else left
    top = format_geometry_literal(metrics.input_padding_top)
    bottom = format_geometry_literal(metrics.input_padding_bottom or 0.0)
    left_lit = format_geometry_literal(left)
    right_lit = format_geometry_literal(right)
    return f"contentPadding: EdgeInsets.fromLTRB({left_lit}, {top}, {right_lit}, {bottom})"


def _stack_input_decoration(
    surface: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    hint: str,
    *,
    host_node: CleanDesignTreeNode | None = None,
    field_height: float | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    surface_on_container: bool = False,
    suffix_icon: str | None = None,
    vertical_center: bool = False,
) -> str:
    """Build ``InputDecoration`` for heuristic input stacks."""
    hint_text = escape_dart_string(hint)
    fields = [f"hintText: '{hint_text}'"]
    if hint_node is not None:
        fields.append(
            f"hintStyle: {text_style_expr(hint_node, bundled_font_families=bundled_font_families, dart_weight_overrides_by_family=dart_weight_overrides_by_family, text_theme_slot_by_style_name=text_theme_slot_by_style_name, text_theme_size_slots=text_theme_size_slots)}"
        )
    if surface_on_container:
        padding = None
        if vertical_center:
            padding = _optical_single_line_input_content_padding(
                host_node,
                hint_node,
                field_height,
            )
        if padding is None and host_node is not None and host_node.layout_slot is not None:
            padding = _planner_input_content_padding(host_node)
        if padding is None:
            padding = _input_content_padding(surface, hint_node, field_height)
        if padding is None and host_node is not None:
            padding = _flex_input_content_padding(host_node, hint_node, field_height)
        if padding is not None:
            fields.append(padding)
        else:
            left = 20.0
            if (
                hint_node is not None
                and hint_node.stack_placement is not None
                and hint_node.stack_placement.left is not None
            ):
                left = hint_node.stack_placement.left
            fields.append(
                f"contentPadding: EdgeInsets.symmetric(horizontal: {left}, vertical: 0)"
            )
        fields.append("border: InputBorder.none")
        fields.append("enabledBorder: InputBorder.none")
        fields.append("focusedBorder: InputBorder.none")
        fields.append("disabledBorder: InputBorder.none")
        fields.append("errorBorder: InputBorder.none")
        fields.append("focusedErrorBorder: InputBorder.none")
    else:
        padding = _input_content_padding(surface, hint_node, field_height)
        if padding is not None:
            fields.append(padding)
        if surface is not None and surface.style.background_color:
            fields.append("filled: true")
            fields.append(f"fillColor: {dart_color_expr(surface.style)}")
        radius = surface.style.border_radius if surface is not None else None
        if radius is not None:
            fields.append(
                "border: OutlineInputBorder("
                f"borderRadius: BorderRadius.circular({radius}), "
                "borderSide: BorderSide.none"
                ")"
            )
            fields.append(
                "enabledBorder: OutlineInputBorder("
                f"borderRadius: BorderRadius.circular({radius}), "
                "borderSide: BorderSide.none"
                ")"
            )
    if suffix_icon is not None:
        fields.append(f"suffixIcon: {suffix_icon}")
    return f"InputDecoration({', '.join(fields)})"


def _input_text_style_expr(
    node: CleanDesignTreeNode,
    *,
    hint_node: CleanDesignTreeNode | None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
    vertical_center: bool = False,
) -> str:
    """Prefer prefilled value typography over the field label for ``TextField.style``."""
    value_node = input_value_style_node(node)
    style_node = value_node or hint_node
    if style_node is not None:
        return text_style_expr(
            style_node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    return "Theme.of(context).textTheme.bodyMedium"


def _render_stack_input(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    embed_in_trailing_row: bool = False,
) -> str:
    """Render a positioned ``TextField`` for classic absolute input groups."""
    surface = input_surface_node(node) or interaction_surface_node(node)
    hint_node = input_hint_node(node)
    hint = input_hint_text(node)
    width, height = _node_layout_size(surface or node, node.stack_placement)
    field_height = surface.sizing.height if surface is not None else height
    vertical_center = field_height is not None and field_height > 0
    decoration = _stack_input_decoration(
        surface,
        hint_node,
        hint,
        host_node=node,
        field_height=field_height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=surface is not None
        and surface.style.background_color is not None,
        vertical_center=vertical_center,
    )
    obscure = (
        "true"
        if looks_like_password_field_stack(node) or "password" in hint.lower()
        else "false"
    )
    input_style = _input_text_style_expr(
        node,
        hint_node=hint_node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        vertical_center=vertical_center,
    )
    value_text = input_flex_value_text(node)
    if value_text:
        escaped_value = escape_dart_string(value_text)
        field = (
            f"TextField("
            f"controller: TextEditingController(text: '{escaped_value}'), "
            f"obscureText: {obscure}, "
            f"style: {input_style}, decoration: {decoration})"
        )
    else:
        field = f"TextField(obscureText: {obscure}, style: {input_style}, decoration: {decoration})"
    if not embed_in_trailing_row:
        box_decoration = (
            box_decoration_expr(
                surface.style,
                width=surface.sizing.width,
                height=surface.sizing.height,
            )
            if surface is not None
            else None
        )
        if (
            box_decoration is not None
            and width is not None
            and width > 0
            and height is not None
            and height > 0
        ):
            field = (
                f"Container("
                f"width: {width}, height: {height}, "
                f"decoration: {box_decoration}, "
                f"child: {field}"
                f")"
            )
        elif width is not None and width > 0 and height is not None and height > 0:
            field = f"SizedBox(width: {width}, height: {height}, child: {field})"
        elif width is not None and width > 0:
            field = f"SizedBox(width: {width}, child: {field})"
    elif height is not None and height > 0:
        field = f"SizedBox(height: {height}, child: {field})"
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    label = escape_dart_string(node.accessibility_label or hint)
    field = f"Semantics(label: '{label}', child: {field})"
    return _finalize_widget(node, field, parent_type=parent_type)


def _render_textarea_field(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
) -> str:
    """Render a multiline ``TextField`` for Figma Textarea shells."""
    from figma_flutter_agent.generator.layout.scroll import padding_edge_insets
    from figma_flutter_agent.parser.interaction import textarea_hint_node

    hint_node = textarea_hint_node(node)
    hint_raw = (hint_node.text if hint_node is not None else None) or node.accessibility_label or "Comment"
    hint = escape_dart_string(hint_raw)
    input_style = (
        text_style_expr(
            hint_node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if hint_node is not None
        else "Theme.of(context).textTheme.bodyMedium"
    )
    height = node.sizing.height
    min_lines = 3
    if height is not None and float(height) >= 120.0:
        min_lines = 4
    content_padding = padding_edge_insets(node) or "const EdgeInsets.fromLTRB(16.0, 12.0, 16.0, 12.0)"
    field = (
        f"TextField("
        f"maxLines: null, "
        f"minLines: {min_lines}, "
        f"style: {input_style}, "
        f"decoration: InputDecoration("
        f"hintText: '{hint}', "
        f"border: InputBorder.none, "
        f"contentPadding: {content_padding}"
        f"))"
    )
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    box_decoration = box_decoration_expr(
        node.style,
        width=node.sizing.width,
        height=node.sizing.height,
    )
    if box_decoration is not None:
        field = f"Container(decoration: {box_decoration}, child: {field})"
    if height is not None and float(height) > 0:
        field = f"SizedBox(height: {format_geometry_literal(float(height))}, child: {field})"
    label = escape_dart_string(node.accessibility_label or hint_raw)
    return _finalize_widget(
        node,
        f"Semantics(label: '{label}', child: {field})",
        parent_type=parent_type,
    )


def _find_icon_glyph_expr(node: CleanDesignTreeNode) -> str | None:
    """Resolve a Material icon fallback for vector chrome under a tap target."""
    from figma_flutter_agent.parser.interaction import (
        looks_like_favorite_icon_button,
        looks_like_plus_icon_button,
        stroke_close_icon_expr,
        stroke_minus_icon_expr,
        stroke_plus_icon_expr,
    )

    if looks_like_plus_icon_button(node):
        side = min(
            float(node.sizing.width or 40.0),
            float(node.sizing.height or 40.0),
        )
        icon_size = max(min(side * 0.35, 18.0), 14.0)
        return (
            "Icon(Icons.add, "
            "color: Color(0xFFFFFFFF), "
            f"size: {format_geometry_literal(icon_size)})"
        )

    if looks_like_favorite_icon_button(node):
        color = "Color(0xFF3E4A3C)"
        for child in node.children:
            if child.type == NodeType.VECTOR and child.style.background_color:
                color = dart_color_expr(child.style, fallback="0xFF3E4A3C")
                break
        side = min(
            float(node.sizing.width or 32.0),
            float(node.sizing.height or 32.0),
        )
        icon_size = max(min(side * 0.45, 18.0), 14.0)
        return (
            "Icon(Icons.favorite_border, "
            f"color: {color}, "
            f"size: {format_geometry_literal(icon_size)})"
        )

    for resolver in (
        stroke_plus_icon_expr,
        stroke_minus_icon_expr,
        stroke_close_icon_expr,
    ):
        glyph = resolver(node)
        if glyph is not None:
            return glyph
    fallback = _render_stroke_glyph_fallback(node)
    if fallback is not None:
        return fallback
    for child in node.children:
        found = _find_icon_glyph_expr(child)
        if found is not None:
            return found
    return None


def _find_trailing_input_icon_expr(node: CleanDesignTreeNode) -> str | None:
    """Resolve a stroke/icon fallback for compact INPUT trailing chrome."""
    return _find_icon_glyph_expr(node)


def _render_input_trailing_suffix_icon(
    chrome: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Compact ``InputDecoration.suffixIcon`` for calendar/chevron chrome."""
    del uses_svg, theme_variant, bundled_font_families, dart_weight_overrides_by_family
    del text_theme_slot_by_style_name, text_theme_size_slots
    from figma_flutter_agent.generator.layout.cupertino import _on_pressed_handler

    icon_expr = _find_trailing_input_icon_expr(chrome) or (
        "Icon(Icons.calendar_today_outlined, size: 18.0)"
    )
    on_pressed = _on_pressed_handler(chrome.id, "button-action")
    return (
        "IconButton("
        f"icon: {icon_expr}, "
        "padding: EdgeInsets.zero, "
        "visualDensity: VisualDensity.compact, "
        "constraints: const BoxConstraints(minWidth: 32, minHeight: 32), "
        f"{on_pressed}"
        ")"
    )


def _render_flex_input_with_trailing_chrome(
    node: CleanDesignTreeNode,
    trailing: list[CleanDesignTreeNode],
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    uses_svg: bool,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Render prefilled flex inputs; display rows hug value copy like profile fields."""
    surface = input_surface_node(node)
    hint_node = input_hint_node(node)
    value_text = input_flex_value_text(node)
    width, height = _node_layout_size(surface or node, node.stack_placement)

    suffix_icon = _render_input_trailing_suffix_icon(
        trailing[0],
        uses_svg=uses_svg,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    hint = input_hint_text(node)
    field_height = surface.sizing.height if surface is not None else height
    vertical_center = field_height is not None and field_height > 0
    decoration = _stack_input_decoration(
        surface,
        hint_node,
        hint,
        host_node=node,
        field_height=field_height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=surface is not None
        and surface.style.background_color is not None,
        suffix_icon=suffix_icon,
        vertical_center=vertical_center,
    )
    obscure = (
        "true"
        if looks_like_password_field_stack(node) or "password" in hint.lower()
        else "false"
    )
    input_style = _input_text_style_expr(
        node,
        hint_node=hint_node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        vertical_center=vertical_center,
    )
    if value_text:
        escaped_value = escape_dart_string(value_text)
        field = (
            f"TextField("
            f"controller: TextEditingController(text: '{escaped_value}'), "
            f"obscureText: {obscure}, "
            f"style: {input_style}, decoration: {decoration})"
        )
    else:
        field = f"TextField(obscureText: {obscure}, style: {input_style}, decoration: {decoration})"
    if height is not None and height > 0:
        field = f"SizedBox(height: {height}, child: {field})"
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    box_decoration = (
        box_decoration_expr(
            surface.style,
            width=surface.sizing.width,
            height=surface.sizing.height,
        )
        if surface is not None
        else None
    )
    if (
        box_decoration is not None
        and width is not None
        and width > 0
        and height is not None
        and height > 0
    ):
        composed = (
            f"Container(width: {width}, height: {height}, "
            f"decoration: {box_decoration}, child: {field})"
        )
    else:
        composed = field
    label = escape_dart_string(node.accessibility_label or input_hint_text(node))
    return _finalize_widget(
        node,
        f"Semantics(label: '{label}', child: {composed})",
        parent_type=parent_type,
    )


