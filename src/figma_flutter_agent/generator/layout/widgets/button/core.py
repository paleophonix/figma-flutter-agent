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
    looks_like_compact_icon_action_stack,
    looks_like_play_pause_control_stack,
    looks_like_skip_control_stack,
    primary_surface_node,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, SizingMode

from ..playback import _sizing_like_skip_control


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
    from figma_flutter_agent.parser.interaction import host_prefers_intrinsic_extent

    intrinsic_height = host_prefers_intrinsic_extent(node)
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


__all__ = [
    "_button_ink_surface_params",
    "_stack_uses_circular_ink",
    "_wrap_button_stack",
]
