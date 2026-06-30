"""Box decoration and border style expressions."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import (
    _argb_hex_literal,
    _normalize_hex_color,
    dart_color_expr,
    gradient_fill_expr,
)
from figma_flutter_agent.generator.render_units import (
    figma_spread_to_flutter_spread,
    format_figma_blur_radius_literal,
    hairline_border_width,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
)
from figma_flutter_agent.schemas import NodeStyle, ShadowEffect


def card_elevation_expr(style: NodeStyle) -> str:
    """Build a Dart elevation expression for Material cards."""
    if style.elevation is not None:
        return str(style.elevation)
    return "0"


def card_emit_needs_material_shell(style: NodeStyle) -> bool:
    """Return True when a card shell should emit a Material surface."""
    if style.elevation is not None and float(style.elevation) > 0:
        return True
    if style.background_color:
        return True
    return bool(style.effects)


_MAX_SANE_BORDER_RADIUS = 512.0


def _resolved_border_radius(
    style: NodeStyle,
    *,
    frame_width: float | None = None,
    frame_height: float | None = None,
) -> float | None:
    """Normalize Figma corner radii, including pill tokens encoded as huge values."""
    radius = style.border_radius
    if radius is None:
        css_radius = style.css_properties.get("border-radius")
        if css_radius is not None:
            try:
                radius = float(css_radius.replace("px", "").strip())
            except ValueError:
                radius = None
    if radius is None:
        return None
    if radius <= _MAX_SANE_BORDER_RADIUS:
        return radius
    if frame_height is not None and frame_height > 0:
        return float(frame_height) / 2.0
    if frame_width is not None and frame_width > 0:
        return float(frame_width) / 2.0
    return _MAX_SANE_BORDER_RADIUS


def border_radius_expr(
    style: NodeStyle,
    *,
    frame_width: float | None = None,
    frame_height: float | None = None,
) -> str:
    """Build a Dart border radius expression."""
    corners = style.border_radius_corners
    if corners is not None:
        return (
            "BorderRadius.only("
            f"topLeft: Radius.circular({format_micro_style_literal(corners.top_left)}), "
            f"topRight: Radius.circular({format_micro_style_literal(corners.top_right)}), "
            f"bottomRight: Radius.circular({format_micro_style_literal(corners.bottom_right)}), "
            f"bottomLeft: Radius.circular({format_micro_style_literal(corners.bottom_left)}))"
        )
    radius = _resolved_border_radius(
        style,
        frame_width=frame_width,
        frame_height=frame_height,
    )
    if radius is None:
        return "BorderRadius.circular(AppSpacing.md)"
    return f"BorderRadius.circular({format_geometry_literal(radius)})"


def _shadow_expr(effect: ShadowEffect) -> str:
    color = f"Color({_argb_hex_literal(effect.color)})"
    blur_radius = format_figma_blur_radius_literal(effect.blur)
    spread_radius = format_geometry_literal(figma_spread_to_flutter_spread(effect.spread))
    return (
        f"BoxShadow("
        f"offset: Offset({format_geometry_literal(effect.offset_x)}, "
        f"{format_geometry_literal(effect.offset_y)}), "
        f"blurRadius: {blur_radius}, "
        f"spreadRadius: {spread_radius}, "
        f"color: {color}"
        f")"
    )


def _partition_shadow_effects(
    effects: list[ShadowEffect] | None,
) -> tuple[list[ShadowEffect], list[ShadowEffect]]:
    """Split Figma shadow effects into outer drops and inner inset bands."""
    drops: list[ShadowEffect] = []
    inners: list[ShadowEffect] = []
    for effect in effects or []:
        if effect.kind == "drop":
            drops.append(effect)
        elif effect.kind == "inner":
            inners.append(effect)
    return drops, inners


_MIN_VISIBLE_INNER_SEPARATOR_ALPHA = 0x40


def _inner_shadow_color_expr(effect: ShadowEffect) -> str:
    """Emit a separator inner shadow color with a visible alpha floor."""
    color = effect.color or "0xFF000000"
    if not color.startswith("0x") or len(color) < 10:
        return f"Color({_argb_hex_literal(color)})"
    alpha = int(color[2:4], 16)
    rgb = color[4:]
    if alpha < _MIN_VISIBLE_INNER_SEPARATOR_ALPHA:
        color = f"0x{_MIN_VISIBLE_INNER_SEPARATOR_ALPHA:02X}{rgb}"
    return f"Color({_argb_hex_literal(color)})"


def _inner_shadow_band_height(
    effect: ShadowEffect,
    frame_height: float | None,
) -> float:
    """Visible inset band height derived from offset, blur, and spread."""
    band = abs(float(effect.offset_y)) + float(effect.blur)
    if effect.spread:
        band += abs(float(effect.spread))
    if frame_height is not None and frame_height > 0:
        band = min(band, float(frame_height) * 0.5)
    return max(band, 1.0)


def _inner_shadow_overlay_expr(
    effect: ShadowEffect,
    *,
    border_radius_expr: str | None,
    frame_height: float | None,
) -> str:
    """Emit a clipped inset highlight band (Flutter has no native inner shadow)."""
    color = _inner_shadow_color_expr(effect)
    band_lit = format_geometry_literal(_inner_shadow_band_height(effect, frame_height))
    radius_field = ""
    if border_radius_expr is not None:
        radius_field = f"borderRadius: {border_radius_expr}, "
    if effect.offset_y > 0:
        gradient = (
            f"LinearGradient("
            f"begin: Alignment.bottomCenter, "
            f"end: Alignment.topCenter, "
            f"colors: [{color}, {color}.withOpacity(0.0)]"
            f")"
        )
        position_fields = f"bottom: 0, left: 0, right: 0, height: {band_lit}"
    else:
        gradient = (
            f"LinearGradient("
            f"begin: Alignment.topCenter, "
            f"end: Alignment.bottomCenter, "
            f"colors: [{color}, {color}.withOpacity(0.0)]"
            f")"
        )
        position_fields = f"top: 0, left: 0, right: 0, height: {band_lit}"
    return (
        f"Positioned("
        f"{position_fields}, "
        f"child: IgnorePointer("
        f"child: DecoratedBox("
        f"decoration: BoxDecoration(gradient: {gradient}, {radius_field}), "
        f"child: const SizedBox.shrink()"
        f")"
        f")"
        f")"
    )


def inner_shadow_overlay_exprs(
    style: NodeStyle,
    *,
    frame_width: float | None = None,
    frame_height: float | None = None,
) -> list[str]:
    """Build inset overlay widgets for all inner shadow effects on a style."""
    _, inners = _partition_shadow_effects(style.effects)
    if not inners:
        return []
    radius = border_radius_expr(style, frame_width=frame_width, frame_height=frame_height)
    return [
        _inner_shadow_overlay_expr(
            effect,
            border_radius_expr=radius,
            frame_height=frame_height,
        )
        for effect in inners
    ]


def wrap_with_inner_shadow_overlays(
    widget: str,
    overlays: list[str],
    *,
    border_radius_expr: str | None,
) -> str:
    """Clip and stack non-interactive inset shadow bands above a painted surface."""
    if not overlays:
        return widget
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        strip_flex_parent_data_deep,
    )

    inner = strip_flex_parent_data_deep(widget)
    stack = f"Stack(fit: StackFit.passthrough, children: [{inner}, {', '.join(overlays)}])"
    if border_radius_expr is not None:
        return f"ClipRRect(borderRadius: {border_radius_expr}, child: {stack})"
    return f"ClipRect(child: {stack})"


def _border_color_expr(style: NodeStyle) -> str | None:
    raw = style.border_color or style.css_properties.get("border-color")
    if raw is None:
        return None
    hex_literal = _normalize_hex_color(raw)
    if hex_literal is None:
        hex_literal = _argb_hex_literal(raw)
    return f"Color({hex_literal})"


def _resolved_border_width(
    border_width: float,
    *,
    stroke_align: str | None = None,
) -> float:
    """Map Figma strokes to Flutter border widths.

    INSIDE component strokes keep their logical Figma weight at runtime.
    OUTSIDE strokes still snap to a comparison hairline for golden parity (FID-45).
    """
    if (stroke_align or "").upper() == "INSIDE":
        return border_width
    if 0.75 <= border_width <= 1.25:
        return hairline_border_width()
    return border_width


def box_decoration_expr(
    style: NodeStyle,
    *,
    width: float | None = None,
    height: float | None = None,
    omit_shadows: bool = False,
    omit_fill: bool = False,
) -> str | None:
    """Build an optional BoxDecoration expression from Dev Mode style metadata."""
    fields: list[str] = []
    if style.gradient:
        gradient = gradient_fill_expr(style.gradient)
        if gradient is not None:
            fields.append(f"gradient: {gradient}")
    elif not omit_fill and (style.background_color or style.css_properties.get("background-color")):
        fields.append(f"color: {dart_color_expr(style)}")
    elif not omit_fill and style.border_color and style.border_width and style.border_width > 0:
        fields.append("color: const Color(0xFFFFFFFF)")
    radius = _resolved_border_radius(
        style,
        frame_width=width,
        frame_height=height,
    )
    is_circle = (
        radius is not None
        and width is not None
        and height is not None
        and width > 0
        and height > 0
        and radius >= min(width, height) / 2.0 - 1.0
        and abs(width - height) <= 2.0
    )
    if is_circle:
        fields.append("shape: BoxShape.circle")
    elif radius is not None or style.border_radius_corners is not None:
        fields.append(
            f"borderRadius: {border_radius_expr(style, frame_width=width, frame_height=height)}"
        )
    border_color = _border_color_expr(style)
    border_width = style.border_width
    if border_width is None:
        css_width = style.css_properties.get("border-width")
        if css_width is not None:
            try:
                border_width = float(css_width.replace("px", "").strip())
            except ValueError:
                border_width = None
    if (
        border_color is not None
        and border_width is not None
        and border_width > 0
        and ((style.stroke_align or "").upper() != "OUTSIDE")
    ):
        resolved_width = _resolved_border_width(
            border_width,
            stroke_align=style.stroke_align,
        )
        fields.append(f"border: Border.all(color: {border_color}, width: {resolved_width})")
    if style.effects and not omit_shadows:
        drop_effects, _ = _partition_shadow_effects(style.effects)
        shadow_exprs = [_shadow_expr(effect) for effect in drop_effects]
        if shadow_exprs:
            fields.append(f"boxShadow: [{', '.join(shadow_exprs)}]")
    if not fields:
        return None
    return f"BoxDecoration({', '.join(fields)})"


def box_foreground_decoration_expr(style: NodeStyle) -> str | None:
    """Build ``foregroundDecoration`` for OUTSIDE strokes (FID-47)."""
    if (style.stroke_align or "").upper() != "OUTSIDE":
        return None
    border_color = _border_color_expr(style)
    border_width = style.border_width
    if border_width is None:
        css_width = style.css_properties.get("border-width")
        if css_width is not None:
            try:
                border_width = float(css_width.replace("px", "").strip())
            except ValueError:
                border_width = None
    if border_color is None or border_width is None or border_width <= 0:
        return None
    radius = _resolved_border_radius(style)
    resolved_width = _resolved_border_width(
        border_width,
        stroke_align=style.stroke_align,
    )
    fields = [f"border: Border.all(color: {border_color}, width: {resolved_width})"]
    if radius is not None or style.border_radius_corners is not None:
        fields.append(f"borderRadius: {border_radius_expr(style)}")
    return f"BoxDecoration({', '.join(fields)})"


def has_box_decoration(style: NodeStyle) -> bool:
    """Return True when the node style warrants a Container decoration."""
    if box_decoration_expr(style) is not None:
        return True
    border_color = _border_color_expr(style)
    border_width = style.border_width
    if border_width is None:
        css_width = style.css_properties.get("border-width")
        if css_width is not None:
            try:
                border_width = float(css_width.replace("px", "").strip())
            except ValueError:
                border_width = None
    return border_color is not None and border_width is not None and border_width > 0
