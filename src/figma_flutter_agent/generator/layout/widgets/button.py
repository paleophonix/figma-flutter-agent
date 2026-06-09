"""Button, link, consent-checkbox, and CTA-footer stack emitters."""

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

from .shared import _node_layout_size, figma_positioned_dimensions
from .decoration import (
    _decorate_widget_with_box_decoration,
    _wrap_frosted_layer_blur,
    _wrap_widget_with_box_decoration,
)
from .layout import (
    _button_list_tile_row_body,
    _flex_parent_data_wrapper,
    _flex_spacing_field,
    _hoist_flex_parent_data,
    _positioned_fields,
    _positioned_fields_from_pins,
    _stack_has_bottom_anchored_child,
    _wrap_center_preserving_flex_parent_data,
    _wrap_sizing,
)
from .position import (
    _child_needs_positioned_bounds,
    _ensure_positioned_stack_bounds,
    _node_has_nested_stack,
    _render_leaf_surface,
    _wrap_root_stack_viewport,
)
from .playback import _sizing_like_skip_control
from .svg import (
    _apply_node_transform,
    _is_composite_icon_stack,
    _is_skip_control_stack,
    _render_svg_picture,
)
from .text import _apply_stack_position, _position_button_stack_label

def _wrap_link_text(widget: str) -> str:
    """Wrap a text widget with a tappable link affordance."""
    return (
        "MouseRegion("
        "cursor: SystemMouseCursors.click, "
        f"child: GestureDetector(onTap: () {{}}, behavior: HitTestBehavior.opaque, child: {widget})"
        ")"
    )


def _button_ink_surface_params(
    surface: CleanDesignTreeNode,
) -> tuple[str | None, str | None]:
    """Return fill color and optional border for Material ``Ink`` on tap targets."""
    from figma_flutter_agent.generator.layout.style.decoration import (
        _border_color_expr,
        _resolved_border_width,
    )

    fill = (
        dart_color_expr(surface.style)
        if surface.style.background_color is not None
        else "const Color(0xFFFFFFFF)"
    )
    border = None
    border_width = surface.style.border_width or 0.0
    border_color = _border_color_expr(surface.style)
    if (
        border_color is not None
        and border_width > 0
        and (surface.style.opacity is None or surface.style.opacity > 0.01)
    ):
        resolved_width = _resolved_border_width(
            border_width,
            stroke_align=surface.style.stroke_align,
        )
        border = f"Border.all(color: {border_color}, width: {resolved_width})"
    return fill, border


def _is_consent_checkbox_row_stack(node: CleanDesignTreeNode) -> bool:
    """Synthetic row from ``reconcile_consent_checkbox_rows_in_tree``."""
    return node.type == NodeType.STACK and (
        node.name == "ConsentRow" or str(node.id).endswith("-consent-row")
    )


def _wrap_compact_checkbox_control(widget: str, *, width: float, height: float) -> str:
    """Center a compact checkbox inside its Figma square without tap-target drift."""
    width_lit = format_geometry_literal(width)
    height_lit = format_geometry_literal(height)
    return (
        f"SizedBox(width: {width_lit}, height: {height_lit}, "
        f"child: Center(child: {widget}))"
    )


def _emit_compact_inline_label_text(
    label_child: CleanDesignTreeNode,
    *,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Emit single-line label copy optically centered beside compact controls."""
    align = text_align_expr(label_child.style)
    align_suffix = f", textAlign: {align}" if align else ""
    if label_child.text_spans:
        span_parts = emit_text_span_children_from_node(
            label_child,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        return emit_text_rich(span_parts, text_align_suffix=align_suffix)
    text = escape_dart_string(label_child.text or label_child.name)
    style_expr = text_style_expr(
        label_child,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        omit_line_height=True,
    )
    trailing = text_widget_trailing_params(
        label_child.style,
        text_align_suffix=align_suffix,
        omit_strut=True,
        optical_center=True,
    )
    return f"Text('{text}', style: {style_expr}, {trailing})"


def _try_render_consent_checkbox_row(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render privacy copy and checkbox as one tappable row."""
    if not _is_consent_checkbox_row_stack(node):
        return None
    checkbox_child = next(
        (child for child in node.children if looks_like_checkbox_control(child)),
        None,
    )
    label_child = next(
        (child for child in node.children if child.type == NodeType.TEXT),
        None,
    )
    if checkbox_child is None or label_child is None:
        return None
    text_widget = _emit_compact_inline_label_text(
        label_child,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if is_link_text(label_child.text):
        text_widget = _wrap_link_text(text_widget)
    checkbox_widget = render_checkbox(checkbox_child, theme_variant=theme_variant)
    width = checkbox_child.sizing.width
    height = checkbox_child.sizing.height
    if width is not None and height is not None and width > 0 and height > 0:
        checkbox_widget = _wrap_compact_checkbox_control(
            checkbox_widget,
            width=float(width),
            height=float(height),
        )
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [Expanded(child: {text_widget}), {checkbox_widget}]"
        ")"
    )


def _try_render_checkbox_label_row(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render a checkbox host beside label copy with centered cross-axis alignment."""
    from figma_flutter_agent.parser.interaction import (
        compact_checkbox_leaf,
        row_hosts_checkbox_label_pair,
    )

    if not row_hosts_checkbox_label_pair(node):
        return None
    checkbox_host = next(
        child for child in node.children if compact_checkbox_leaf(child) is not None
    )
    label_child = next(child for child in node.children if child.type == NodeType.TEXT)
    checkbox_node = compact_checkbox_leaf(checkbox_host)
    if checkbox_node is None:
        return None
    text_widget = _emit_compact_inline_label_text(
        label_child,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if is_link_text(label_child.text):
        text_widget = _wrap_link_text(text_widget)
    checkbox_widget = render_checkbox(checkbox_node, theme_variant=theme_variant)
    width = checkbox_node.sizing.width
    height = checkbox_node.sizing.height
    if width is not None and height is not None and width > 0 and height > 0:
        checkbox_widget = _wrap_compact_checkbox_control(
            checkbox_widget,
            width=float(width),
            height=float(height),
        )
    spacing_field = _flex_spacing_field(node)
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"{spacing_field}"
        f"children: [{checkbox_widget}, Expanded(child: {text_widget})]"
        ")"
    )


def _try_render_cta_footer_split_stack(
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
) -> str | None:
    """Render CTA pill + footer link as separate vertical bands with one InkWell on the pill."""
    if node.type != NodeType.STACK:
        return None
    text_nodes = [
        item
        for item in _local_nodes(node, 2)
        if item.type == NodeType.TEXT and item.text
    ]
    if not _stack_spans_primary_button_and_footer_link(node, text_nodes=text_nodes):
        return None
    surface = primary_surface_node(node)
    clip_height = float(surface.sizing.height or 0) if surface is not None else 0.0
    if clip_height <= 0:
        return None
    stack_width = node.sizing.width
    if node.stack_placement is not None and node.stack_placement.width is not None:
        stack_width = node.stack_placement.width
    if stack_width is None or stack_width <= 0:
        return None
    sorted_children = _sort_absolute_stack_children(node.children, is_layout_root=False)
    cta_children = [
        child
        for child in sorted_children
        if not (child.type == NodeType.TEXT and _is_footer_link_text_node(child))
    ]
    if surface is not None:
        cta_children = [child for child in cta_children if child.id != surface.id]
    footer_children = [
        child
        for child in sorted_children
        if child.type == NodeType.TEXT and _is_footer_link_text_node(child)
    ]
    if not cta_children or not footer_children:
        return None
    from .emit import render_node_body  # lazy: avoid button→emit→button cycle
    cta_widgets = [
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
        for child in cta_children
    ]
    cta_body = ", ".join(cta_widgets)
    cta_stack = _wrap_button_stack(
        f"Stack(clipBehavior: Clip.hardEdge, children: [{cta_body}])",
        node,
        theme_variant=theme_variant,
    )
    parts = [
        (
            "Positioned(left: 0.0, top: 0.0, "
            f"width: {format_geometry_literal(stack_width)}, "
            f"height: {format_geometry_literal(clip_height)}, "
            f"child: {cta_stack})"
        ),
    ]
    for footer in footer_children:
        parts.append(
            render_node_body(
                footer,
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
            ),
        )
    return f"Stack(clipBehavior: Clip.none, children: [{', '.join(parts)}])"


def _stack_uses_circular_ink(node: CleanDesignTreeNode) -> bool:
    """Round tap targets (play/pause, skip, compact chrome) need ``CircleBorder`` ripples."""
    if looks_like_play_pause_control_stack(node) or looks_like_skip_control_stack(node):
        return True
    if _sizing_like_skip_control(node):
        return True
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if abs(float(width) - float(height)) > 3.0:
        return False
    size = min(float(width), float(height))
    if size < 28.0 or size > 120.0:
        return False
    if _has_circular_container(_descendant_nodes(node, _BACK_NAV_DESCENDANT_DEPTH)):
        return True
    surface = primary_surface_node(node)
    if surface is not None:
        radius = surface.style.border_radius
        if radius is not None and radius >= size / 2.2:
            return True
    return looks_like_compact_icon_action_stack(node)


def _wrap_button_stack(
    stack_widget: str,
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    tap_role: str = "button-action",
) -> str:
    """Wrap an interactive stack with a theme-appropriate tap target."""
    from figma_flutter_agent.generator.layout.style.decoration import _resolved_border_radius

    surface = interaction_surface_node(node)
    radius = (
        surface.style.border_radius
        if surface is not None and surface.style.border_radius is not None
        else node.style.border_radius
    )
    resolved_radius = _resolved_border_radius(
        surface.style if surface is not None else node.style,
        frame_width=node.sizing.width,
        frame_height=node.sizing.height,
    )
    if resolved_radius is not None:
        radius = resolved_radius
    ink_fill: str | None = None
    ink_border: str | None = None
    if surface is not None:
        ink_fill, ink_border = _button_ink_surface_params(surface)
    if _stack_uses_circular_ink(node) and ink_fill is None:
        wrapped = cupertino_wrap_circular_button_stack(
            stack_widget,
            theme_variant=theme_variant,
            node_id=node.id,
            tap_role=tap_role,
        )
        if variant_blocks_interaction(node):
            return wrapped.replace(
                f"onTap: () {{ {inline_custom_code_comment(custom_code_zone_id(node.id, tap_role))} }}, ",
                "onTap: null, ",
                1,
            )
        return wrapped
    wrapped = cupertino_wrap_button_stack(
        stack_widget,
        theme_variant=theme_variant,
        border_radius=radius,
        ink_fill_color=ink_fill,
        ink_border=ink_border,
        node_id=node.id,
        tap_role=tap_role,
    )
    if variant_blocks_interaction(node):
        wrapped = wrapped.replace(
            f"onTap: () {{ {inline_custom_code_comment(custom_code_zone_id(node.id, tap_role))} }}, ",
            "onTap: null, ",
            1,
        )
    from figma_flutter_agent.parser.interaction import (
        button_has_composite_row_body,
        button_has_list_tile_row_body,
        button_hosts_stacked_text_column,
    )

    intrinsic_height = (
        button_has_composite_row_body(node)
        or button_has_list_tile_row_body(node)
        or button_hosts_stacked_text_column(node)
    )
    from figma_flutter_agent.generator.layout.flex_policy import (
        button_hosts_status_pill,
        horizontal_chip_button_should_hug_width,
    )

    width = node.sizing.width
    height = node.sizing.height
    if horizontal_chip_button_should_hug_width(node) or button_hosts_status_pill(node):
        if button_hosts_status_pill(node):
            wrapped = f"IntrinsicWidth(child: {wrapped})"
        if height is not None and height > 0:
            height_lit = format_geometry_literal(height)
            return f"SizedBox(height: {height_lit}, child: {wrapped})"
        return wrapped
    if width is not None and height is not None and width > 0 and height > 0:
        width_lit = format_geometry_literal(width)
        height_lit = format_geometry_literal(height)
        if node.sizing.width_mode == SizingMode.FILL:
            if intrinsic_height:
                return f"SizedBox(width: double.infinity, child: {wrapped})"
            return (
                f"SizedBox(width: double.infinity, height: {height_lit}, "
                f"child: {wrapped})"
            )
        if intrinsic_height:
            return f"SizedBox(width: {width_lit}, child: {wrapped})"
        return (
            f"SizedBox(width: {width_lit}, height: {height_lit}, child: {wrapped})"
        )
    if node.sizing.width_mode == SizingMode.FILL or (
        width is not None and width >= 64.0
    ):
        if intrinsic_height:
            return f"SizedBox(width: double.infinity, child: {wrapped})"
        height_clause = ""
        if height is not None and height > 0:
            height_clause = f"height: {format_geometry_literal(height)}, "
        return (
            f"SizedBox(width: double.infinity, {height_clause}"
            f"child: {wrapped})"
        )
    return wrapped


