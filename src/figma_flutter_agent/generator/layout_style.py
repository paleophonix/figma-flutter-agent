"""Map clean-tree styles to Dart theme expressions for deterministic codegen."""

from __future__ import annotations

import math
import re

from figma_flutter_agent.fonts.registry import load_font_registry
from figma_flutter_agent.generator.variant_props import (
    variant_font_size,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GradientFill,
    NodeStyle,
    ShadowEffect,
    TextSpanPart,
)

_HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{6})$")
_RGBA_COLOR_RE = re.compile(
    r"rgba\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*([\d.]+)\s*\)"
)


def _normalize_hex_color(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    match = _HEX_COLOR_RE.match(trimmed)
    if match is None:
        return None
    return f"0xFF{match.group(1).upper()}"


def _argb_hex_literal(value: str) -> str:
    normalized = value.removeprefix("0x").removeprefix("0X")
    if len(normalized) == 8:
        return f"0x{normalized.upper()}"
    hex_color = _normalize_hex_color(value)
    if hex_color is not None:
        return hex_color
    return "0xFF000000"


def fill_luminance(value: str | None) -> float | None:
    """Relative luminance in ``[0, 1]`` for an ARGB hex or CSS rgba() fill string."""
    hex_literal = _color_raw_to_hex_literal(value)
    if hex_literal is None:
        return None
    normalized = hex_literal.removeprefix("0x").removeprefix("0X")
    if len(normalized) != 8:
        return None
    red = int(normalized[2:4], 16)
    green = int(normalized[4:6], 16)
    blue = int(normalized[6:8], 16)
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0


def is_dark_fill_color(value: str | None, *, threshold: float = 0.55) -> bool:
    """Return True when a fill reads as visually dark (for control-core detection)."""
    luminance = fill_luminance(value)
    return luminance is not None and luminance < threshold


def _color_raw_to_hex_literal(value: str | None) -> str | None:
    """Resolve ARGB hex from Dev Mode CSS rgba(), #hex, or 0x literals."""
    if value is None:
        return None
    trimmed = value.strip()
    rgba_match = _RGBA_COLOR_RE.match(trimmed)
    if rgba_match is not None:
        red, green, blue, alpha = rgba_match.groups()
        alpha_byte = round(float(alpha) * 255)
        return (
            f"0x{alpha_byte:02X}{int(float(red)):02X}"
            f"{int(float(green)):02X}{int(float(blue)):02X}"
        )
    hex_color = _normalize_hex_color(trimmed)
    if hex_color is not None:
        return hex_color
    if trimmed.startswith("0x") or trimmed.startswith("0X"):
        return _argb_hex_literal(trimmed)
    return None


def dart_color_expr(
    style: NodeStyle,
    *,
    css_key: str = "background-color",
    fallback: str = "AppColors.primary",
    apply_opacity: bool = True,
) -> str:
    """Build a Dart Color expression from node style or CSS properties."""
    if css_key == "color":
        raw = style.css_properties.get("color") or style.text_color
    else:
        raw = style.background_color or style.css_properties.get(css_key) or style.text_color
    hex_literal = _color_raw_to_hex_literal(raw)
    if hex_literal is None:
        return fallback
    color = f"Color({hex_literal})"
    if apply_opacity and style.opacity is not None and 0.0 < style.opacity < 1.0:
        return f"{color}.withOpacity({round(style.opacity, 3)})"
    return color


def gradient_fill_expr(gradient: GradientFill) -> str | None:
    """Build a Dart LinearGradient or RadialGradient expression from Figma fills."""
    if not gradient.stops:
        return None

    colors = ", ".join(f"Color({_argb_hex_literal(stop.color)})" for stop in gradient.stops)
    stop_positions = ", ".join(str(stop.position) for stop in gradient.stops)
    if gradient.type == "radial":
        return f"RadialGradient(colors: [{colors}], stops: [{stop_positions}])"

    angle = gradient.angle if gradient.angle is not None else 180.0
    radians = math.radians(angle - 90.0)
    dx = math.cos(radians)
    dy = math.sin(radians)
    return (
        f"LinearGradient("
        f"begin: Alignment({-dx:.4f}, {-dy:.4f}), "
        f"end: Alignment({dx:.4f}, {dy:.4f}), "
        f"colors: [{colors}], "
        f"stops: [{stop_positions}]"
        f")"
    )


def _shadow_expr(effect: ShadowEffect) -> str:
    color = f"Color({_argb_hex_literal(effect.color)})"
    return (
        f"BoxShadow("
        f"offset: Offset({effect.offset_x}, {effect.offset_y}), "
        f"blurRadius: {effect.blur}, "
        f"spreadRadius: {effect.spread}, "
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


def box_decoration_expr(
    style: NodeStyle,
    *,
    width: float | None = None,
    height: float | None = None,
) -> str | None:
    """Build an optional BoxDecoration expression from Dev Mode style metadata."""
    fields: list[str] = []
    if style.gradient:
        gradient = gradient_fill_expr(style.gradient)
        if gradient is not None:
            fields.append(f"gradient: {gradient}")
    elif style.background_color or style.css_properties.get("background-color"):
        fields.append(f"color: {dart_color_expr(style)}")
    elif style.border_color and style.border_width and style.border_width > 0:
        fields.append("color: const Color(0xFFFFFFFF)")
    radius = style.border_radius
    if radius is None:
        css_radius = style.css_properties.get("border-radius")
        if css_radius is not None:
            try:
                radius = float(css_radius.replace("px", "").strip())
            except ValueError:
                radius = None
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
    elif radius is not None:
        fields.append(f"borderRadius: BorderRadius.circular({radius})")
    border_color = _border_color_expr(style)
    border_width = style.border_width
    if border_width is None:
        css_width = style.css_properties.get("border-width")
        if css_width is not None:
            try:
                border_width = float(css_width.replace("px", "").strip())
            except ValueError:
                border_width = None
    if border_color is not None and border_width is not None and border_width > 0:
        fields.append(f"border: Border.all(color: {border_color}, width: {border_width})")
    if style.effects:
        shadows = ", ".join(
            _shadow_expr(effect) for effect in style.effects if effect.kind == "drop"
        )
        if shadows:
            fields.append(f"boxShadow: [{shadows}]")
    if not fields:
        return None
    return f"BoxDecoration({', '.join(fields)})"


def card_elevation_expr(style: NodeStyle) -> str:
    """Build a Dart elevation expression for Material cards."""
    if style.elevation is not None:
        return str(style.elevation)
    return "AppElevation.md"


def border_radius_expr(style: NodeStyle) -> str:
    """Build a Dart border radius expression."""
    radius = style.border_radius
    if radius is None:
        css_radius = style.css_properties.get("border-radius")
        if css_radius is not None:
            try:
                radius = float(css_radius.replace("px", "").strip())
            except ValueError:
                radius = None
    if radius is None:
        return "BorderRadius.circular(AppSpacing.md)"
    return f"BorderRadius.circular({radius})"


_TEXT_ALIGN = {
    "LEFT": "TextAlign.left",
    "CENTER": "TextAlign.center",
    "RIGHT": "TextAlign.right",
    "JUSTIFIED": "TextAlign.justify",
}


def text_align_expr(style: NodeStyle) -> str | None:
    """Map Figma horizontal text alignment to a Dart ``TextAlign`` expression."""
    if not style.text_align:
        return None
    return _TEXT_ALIGN.get(style.text_align.upper())


def _flutter_font_weight_expr(
    style: NodeStyle,
    *,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
) -> str | None:
    """Map Figma weight tokens to Flutter ``FontWeight`` expressions."""
    if not style.font_weight:
        return None
    token = int(style.font_weight.removeprefix("w"))
    if (
        style.font_family
        and bundled_font_families is not None
        and style.font_family in bundled_font_families
    ):
        if dart_weight_overrides_by_family is not None:
            manifest_override = dart_weight_overrides_by_family.get(style.font_family, {}).get(
                style.font_weight
            )
            if manifest_override is not None:
                token = int(manifest_override.removeprefix("w"))
                return f"FontWeight.w{token}"
        profile = load_font_registry().profile_for_pubspec_family(style.font_family)
        if profile is not None:
            override = profile.dart_weight_override(style.font_weight)
            if override is not None:
                token = int(override.removeprefix("w"))
                return f"FontWeight.w{token}"
    return f"FontWeight.w{token}"


def _text_style_fields(
    style: NodeStyle,
    *,
    css_key: str = "color",
    fallback: str = "AppColors.primary",
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    """Build shared ``TextStyle`` field expressions from node style metadata."""
    color = dart_color_expr(style, css_key=css_key, fallback=fallback)
    parts = [f"color: {color}"]
    if style.font_size is not None:
        parts.append(f"fontSize: {style.font_size}")
    if style.font_family:
        parts.append(f"fontFamily: '{style.font_family}'")
        if bundled_font_families is None or style.font_family not in bundled_font_families:
            parts.append("fontFamilyFallback: const ['Arial', 'sans-serif']")
    if style.font_style == "italic":
        parts.append("fontStyle: FontStyle.italic")
    weight_expr = _flutter_font_weight_expr(
        style,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
    )
    if weight_expr is not None:
        parts.append(f"fontWeight: {weight_expr}")
    if style.line_height is not None and (
        bundled_font_families is None
        or not style.font_family
        or style.font_family not in bundled_font_families
    ):
        parts.append(f"height: {round(style.line_height, 4)}")
        parts.append("leadingDistribution: TextLeadingDistribution.proportional")
    if style.letter_spacing is not None:
        parts.append(f"letterSpacing: {round(style.letter_spacing, 2)}")
    return parts


def text_style_expr(
    node: CleanDesignTreeNode,
    *,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
) -> str:
    """Build TextStyle from node style and component variant Size."""
    parts = _text_style_fields(
        node.style,
        css_key="color",
        fallback="AppColors.primary",
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
    )
    if node.style.font_size is None:
        variant_size = variant_font_size(node)
        if variant_size is not None:
            parts.append(f"fontSize: {variant_size}")
    return f"TextStyle({', '.join(parts)})"


def text_span_style_expr(
    part: TextSpanPart,
    base_style: NodeStyle,
    *,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
) -> str:
    """Build a ``TextStyle`` for one rich-text span."""
    style = NodeStyle(
        text_color=part.text_color or base_style.text_color,
        font_size=base_style.font_size,
        font_weight=part.font_weight or base_style.font_weight,
        line_height=base_style.line_height,
        letter_spacing=base_style.letter_spacing,
        font_family=base_style.font_family,
        font_style=base_style.font_style,
    )
    parts = _text_style_fields(
        style,
        css_key="color",
        fallback="AppColors.primary",
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
    )
    if not parts:
        return "const TextStyle()"
    return f"TextStyle({', '.join(parts)})"


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
