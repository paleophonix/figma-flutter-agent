"""Icon glyph resolution for input field trailing chrome."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..decoration import _render_stroke_glyph_fallback

_ON_SURFACE_VARIANT = "Theme.of(context).colorScheme.onSurfaceVariant"
_ON_PRIMARY = "Theme.of(context).colorScheme.onPrimary"


def _find_icon_glyph_expr(node: CleanDesignTreeNode) -> str | None:
    """Resolve a Material icon fallback for vector chrome under a tap target."""
    from figma_flutter_agent.parser.interaction.forms import _is_input_visibility_affordance
    from figma_flutter_agent.parser.interaction import (
        looks_like_favorite_icon_button,
        looks_like_info_icon_button,
        looks_like_plus_icon_button,
        stroke_close_icon_expr,
        stroke_minus_icon_expr,
        stroke_plus_icon_expr,
    )

    if _is_input_visibility_affordance(node):
        color = _ON_SURFACE_VARIANT
        for child in node.children:
            if child.type == NodeType.VECTOR and (
                child.style.has_stroke or child.style.background_color
            ):
                color = dart_color_expr(child.style, fallback=_ON_SURFACE_VARIANT)
                break
        side = min(
            float(node.sizing.width or 20.0),
            float(node.sizing.height or 20.0),
        )
        icon_size = max(min(side * 0.9, 20.0), 16.0)
        return (
            "Icon(Icons.visibility_off_outlined, "
            f"color: {color}, "
            f"size: {format_geometry_literal(icon_size)})"
        )

    if looks_like_info_icon_button(node):
        color = _ON_SURFACE_VARIANT
        for child in node.children:
            if child.type == NodeType.VECTOR and child.style.has_stroke:
                color = dart_color_expr(child.style, fallback=_ON_SURFACE_VARIANT)
                break
        side = min(
            float(node.sizing.width or 32.0),
            float(node.sizing.height or 32.0),
        )
        icon_size = max(min(side * 0.45, 18.0), 14.0)
        return (
            f"Icon(Icons.info_outline, "
            f"color: {color}, "
            f"size: {format_geometry_literal(icon_size)})"
        )

    if looks_like_plus_icon_button(node):
        side = min(
            float(node.sizing.width or 40.0),
            float(node.sizing.height or 40.0),
        )
        icon_size = max(min(side * 0.35, 18.0), 14.0)
        glyph_color = _ON_PRIMARY
        for child in node.children:
            if child.type == NodeType.VECTOR and child.style.background_color:
                glyph_color = dart_color_expr(child.style, fallback=_ON_PRIMARY)
                break
        return (
            f"Icon(Icons.add, color: {glyph_color}, "
            f"size: {format_geometry_literal(icon_size)})"
        )

    if looks_like_favorite_icon_button(node):
        color = _ON_SURFACE_VARIANT
        for child in node.children:
            if child.type == NodeType.VECTOR and child.style.background_color:
                color = dart_color_expr(child.style, fallback=_ON_SURFACE_VARIANT)
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
