"""Core interactive-stack wrapping: tap targets, ink surfaces, and sizing."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_button_stack as cupertino_wrap_button_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_circular_button_stack as cupertino_wrap_circular_button_stack,
)
from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.generator.variant.state import variant_blocks_interaction
from figma_flutter_agent.parser.interaction import (
    _BACK_NAV_DESCENDANT_DEPTH,
    _descendant_nodes,
    _has_circular_container,
    interaction_surface_node,
    layout_fact_compact_icon_action_stack,
    layout_fact_play_pause_control_stack,
    layout_fact_skip_control_stack,
    primary_surface_node,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, GradientFill, SizingMode

from ..playback import _sizing_like_skip_control


def _button_ink_surface_params(
    surface: CleanDesignTreeNode,
) -> tuple[str | None, str | None, list[str], str | None, list[str]]:
    """Return fill color, border, drop shadows, gradient, and inner overlay exprs for ``Ink``."""
    from figma_flutter_agent.generator.layout.style.decoration import (
        _border_color_expr,
        _partition_shadow_effects,
        _resolved_border_width,
        _shadow_expr,
        gradient_fill_expr,
        inner_shadow_overlay_exprs,
    )

    gradient_expr = None
    gradient = surface.style.gradient
    if gradient is not None and not _gradient_reads_as_highlight_shine(gradient):
        gradient_expr = gradient_fill_expr(gradient)

    fill = None
    if gradient_expr is None:
        fill = (
            dart_color_expr(surface.style) if surface.style.background_color is not None else None
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
    drop_effects, _ = _partition_shadow_effects(surface.style.effects)
    shadow_exprs = [_shadow_expr(effect) for effect in drop_effects]
    inner_overlays = inner_shadow_overlay_exprs(
        surface.style,
        frame_width=surface.sizing.width,
        frame_height=surface.sizing.height,
    )
    return fill, border, shadow_exprs, gradient_expr, inner_overlays


def _gradient_stop_luminance(hex_literal: str) -> float:
    """Relative luminance for a ``0xAARRGGBB`` or ``#RRGGBB`` color literal."""
    normalized = hex_literal.strip().upper()
    if normalized.startswith("0X"):
        rgb = normalized[-6:]
    elif normalized.startswith("#"):
        rgb = normalized[1:7]
    else:
        return 0.0
    red = int(rgb[0:2], 16) / 255.0
    green = int(rgb[2:4], 16) / 255.0
    blue = int(rgb[4:6], 16) / 255.0
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _gradient_reads_as_highlight_shine(gradient: GradientFill) -> bool:
    """True for white/translucent gloss overlays, not brand fills."""
    if not gradient.stops:
        return False
    luminous = [_gradient_stop_luminance(stop.color) >= 0.88 for stop in gradient.stops]
    return sum(luminous) >= max(1, len(gradient.stops) - 1)


def _button_shine_overlay_expr(
    surface: CleanDesignTreeNode,
    *,
    border_radius: float | None,
) -> str | None:
    """Optional gloss gradient layer over a solid button fill."""
    from figma_flutter_agent.generator.layout.style.decoration import (
        border_radius_expr,
        gradient_fill_expr,
    )

    gradient = surface.style.gradient
    if gradient is None or not _gradient_reads_as_highlight_shine(gradient):
        return None
    if surface.style.background_color is None:
        return None
    shine = gradient_fill_expr(gradient)
    if shine is None:
        return None
    radius_field = ""
    if border_radius is not None:
        radius_field = f"borderRadius: {border_radius_expr(surface.style, frame_width=surface.sizing.width, frame_height=surface.sizing.height)}, "
    return (
        "Positioned.fill("
        f"child: DecoratedBox("
        f"decoration: BoxDecoration(gradient: {shine}, {radius_field}), "
        "child: const SizedBox.shrink()"
        ")"
        ")"
    )


def _wrap_button_stack_with_shine(
    stack_widget: str,
    *,
    surface: CleanDesignTreeNode,
    border_radius: float | None,
) -> str:
    """Prepend a gloss overlay when the painted surface pairs solid fill + shine."""
    shine = _button_shine_overlay_expr(surface, border_radius=border_radius)
    if shine is None:
        return stack_widget
    return (
        f"Stack(clipBehavior: Clip.none, fit: StackFit.expand, children: [{shine}, {stack_widget}])"
    )


def _stack_uses_circular_ink(node: CleanDesignTreeNode) -> bool:
    """Round tap targets (play/pause, skip, compact chrome) need ``CircleBorder`` ripples."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_icon_tab_slot,
        layout_fact_stack_bottom_nav_tab_glyph_column,
    )

    if layout_fact_stack_bottom_nav_tab_glyph_column(node):
        return False
    if layout_fact_stack_bottom_nav_icon_tab_slot(node):
        return False
    if layout_fact_play_pause_control_stack(node) or layout_fact_skip_control_stack(node):
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
    return layout_fact_compact_icon_action_stack(node)


def _wrap_passive_button_surface(
    stack_widget: str,
    node: CleanDesignTreeNode,
) -> str:
    """Paint button chrome on a passive host that delegates taps to nested buttons."""
    from figma_flutter_agent.generator.layout.style.decoration import _resolved_border_radius

    surface = interaction_surface_node(node)
    style_node = surface if surface is not None else node
    radius = style_node.style.border_radius or node.style.border_radius
    resolved_radius = _resolved_border_radius(
        style_node.style,
        frame_width=node.sizing.width,
        frame_height=node.sizing.height,
    )
    if resolved_radius is not None:
        radius = resolved_radius
    ink_fill, ink_border, shadow_exprs, ink_gradient, inner_overlays = _button_ink_surface_params(
        style_node
    )
    decoration_fields: list[str] = []
    if ink_fill is not None:
        decoration_fields.append(f"color: {ink_fill}")
    if radius is not None:
        decoration_fields.append(
            f"borderRadius: BorderRadius.circular({format_geometry_literal(radius)})"
        )
    if ink_border is not None:
        decoration_fields.append(f"border: {ink_border}")
    if shadow_exprs:
        decoration_fields.append(f"boxShadow: [{', '.join(shadow_exprs)}]")
    if not decoration_fields:
        return stack_widget
    from figma_flutter_agent.generator.layout.style.decoration import (
        border_radius_expr,
        wrap_with_inner_shadow_overlays,
    )

    painted = (
        f"Container(decoration: BoxDecoration({', '.join(decoration_fields)}), "
        f"child: {stack_widget})"
    )
    if not inner_overlays:
        return painted
    radius_expr = border_radius_expr(
        style_node.style,
        frame_width=node.sizing.width,
        frame_height=node.sizing.height,
    )
    return wrap_with_inner_shadow_overlays(
        painted,
        inner_overlays,
        border_radius_expr=radius_expr,
    )


def _wrap_button_stack(
    stack_widget: str,
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    tap_role: str = "button-action",
    band_height: float | None = None,
) -> str:
    """Wrap an interactive stack with a theme-appropriate tap target."""
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        strip_flex_parent_data_deep,
    )
    from figma_flutter_agent.generator.layout.style.decoration import _resolved_border_radius

    stack_widget = strip_flex_parent_data_deep(stack_widget)
    from figma_flutter_agent.parser.interaction.buttons import button_painted_overlay_surface

    surface = button_painted_overlay_surface(node) or interaction_surface_node(node)
    frame_height = band_height if band_height is not None else node.sizing.height
    radius = (
        surface.style.border_radius
        if surface is not None and surface.style.border_radius is not None
        else node.style.border_radius
    )
    resolved_radius = _resolved_border_radius(
        surface.style if surface is not None else node.style,
        frame_width=node.sizing.width,
        frame_height=frame_height,
    )
    if resolved_radius is not None:
        radius = resolved_radius
    ink_fill: str | None = None
    ink_border: str | None = None
    ink_shadows: list[str] = []
    ink_inner_overlays: list[str] = []
    ink_gradient: str | None = None
    from figma_flutter_agent.parser.interaction import layout_fact_compact_icon_action_button

    if node.vector_asset_key and layout_fact_compact_icon_action_button(node):
        pass
    elif surface is not None:
        ink_fill, ink_border, ink_shadows, ink_gradient, ink_inner_overlays = (
            _button_ink_surface_params(surface)
        )
    from figma_flutter_agent.parser.interaction import (
        button_hosts_nested_interactive_buttons,
        host_prefers_intrinsic_extent,
    )

    if surface is not None:
        stack_widget = _wrap_button_stack_with_shine(
            stack_widget,
            surface=surface,
            border_radius=radius,
        )

    if button_hosts_nested_interactive_buttons(node):
        wrapped = _wrap_passive_button_surface(stack_widget, node)
    elif _stack_uses_circular_ink(node) and ink_fill is None:
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
    else:
        wrapped = cupertino_wrap_button_stack(
            stack_widget,
            theme_variant=theme_variant,
            border_radius=radius,
            ink_fill_color=ink_fill,
            ink_gradient=ink_gradient,
            ink_border=ink_border,
            ink_box_shadows=ink_shadows,
            ink_inner_overlays=ink_inner_overlays,
            node_id=node.id,
            tap_role=tap_role,
        )
        if variant_blocks_interaction(node):
            wrapped = wrapped.replace(
                f"onTap: () {{ {inline_custom_code_comment(custom_code_zone_id(node.id, tap_role))} }}, ",
                "onTap: null, ",
                1,
            )

    intrinsic_height = host_prefers_intrinsic_extent(node)
    from figma_flutter_agent.generator.layout.flex_policy import (
        button_hosts_status_pill,
        horizontal_chip_button_should_hug_width,
    )

    width = node.sizing.width
    height = frame_height
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
            return f"SizedBox(width: double.infinity, height: {height_lit}, child: {wrapped})"
        if intrinsic_height:
            return f"SizedBox(width: {width_lit}, child: {wrapped})"
        return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {wrapped})"
    if node.sizing.width_mode == SizingMode.FILL or (width is not None and width >= 64.0):
        if intrinsic_height:
            return f"SizedBox(width: double.infinity, child: {wrapped})"
        height_clause = ""
        if height is not None and height > 0:
            height_clause = f"height: {format_geometry_literal(height)}, "
        return f"SizedBox(width: double.infinity, {height_clause}child: {wrapped})"
    return wrapped


def render_compact_icon_host_stack_body(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str | None:
    """Emit plate + inset foreground glyph layers for compact icon hosts."""
    from figma_flutter_agent.generator.layout.common import escape_dart_string
    from figma_flutter_agent.generator.layout.widgets.svg import _render_svg_picture
    from figma_flutter_agent.parser.interaction.icons import compact_icon_host_layers

    plate, foreground = compact_icon_host_layers(node)
    if foreground is None:
        return None
    host_width = float(node.sizing.width or 0.0)
    host_height = float(node.sizing.height or 0.0)
    parts: list[str] = []
    if plate is not None and plate.vector_asset_key and uses_svg:
        plate_svg = _render_svg_picture(plate, escape_dart_string(plate.vector_asset_key))
        if host_width > 0 and host_height > 0:
            parts.append(
                "Center("
                f"child: SizedBox("
                f"width: {format_geometry_literal(host_width)}, "
                f"height: {format_geometry_literal(host_height)}, "
                f"child: {plate_svg}))"
            )
        else:
            parts.append(plate_svg)
    if foreground.vector_asset_key and uses_svg:
        glyph_width = float(foreground.sizing.width or 24.0)
        glyph_height = float(foreground.sizing.height or 24.0)
        glyph = _render_svg_picture(
            foreground,
            escape_dart_string(foreground.vector_asset_key),
        )
        parts.append(
            "Center("
            f"child: SizedBox("
            f"width: {format_geometry_literal(glyph_width)}, "
            f"height: {format_geometry_literal(glyph_height)}, "
            f"child: {glyph}))"
        )
    if not parts:
        return None
    if host_width > 0 and host_height > 0:
        stack = (
            "Stack("
            "clipBehavior: Clip.none, "
            "alignment: Alignment.center, "
            f"children: [{', '.join(parts)}]"
            ")"
        )
        return (
            f"SizedBox("
            f"width: {format_geometry_literal(host_width)}, "
            f"height: {format_geometry_literal(host_height)}, "
            f"child: {stack})"
        )
    return (
        "Stack("
        "clipBehavior: Clip.none, "
        "alignment: Alignment.center, "
        f"children: [{', '.join(parts)}]"
        ")"
    )


__all__ = [
    "_button_ink_surface_params",
    "_stack_uses_circular_ink",
    "_wrap_passive_button_surface",
    "_wrap_button_stack",
    "render_compact_icon_host_stack_body",
]
