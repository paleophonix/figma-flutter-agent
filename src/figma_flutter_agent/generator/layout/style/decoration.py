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
    return "AppElevation.md"


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
    elif not omit_fill and (
        style.background_color or style.css_properties.get("background-color")
    ):
        fields.append(f"color: {dart_color_expr(style)}")
    elif (
        not omit_fill
        and style.border_color
        and style.border_width
        and style.border_width > 0
    ):
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
    if border_color is not None and border_width is not None and border_width > 0 and (
        (style.stroke_align or "").upper() != "OUTSIDE"
    ):
        resolved_width = _resolved_border_width(
            border_width,
            stroke_align=style.stroke_align,
        )
        fields.append(f"border: Border.all(color: {border_color}, width: {resolved_width})")
    if style.effects and not omit_shadows:
        shadow_exprs = [
            _shadow_expr(effect)
            for effect in style.effects
            if effect.kind in {"drop", "inner"}
        ]
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
