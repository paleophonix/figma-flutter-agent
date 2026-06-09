"""Color and gradient style expressions."""

from __future__ import annotations

import math
import re

from figma_flutter_agent.schemas import GradientFill, NodeStyle

_STRUT_LEADING_EPSILON = 0.5
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
        trimmed_fallback = fallback.strip()
        if trimmed_fallback.startswith("0x") or trimmed_fallback.startswith("0X"):
            return f"Color({trimmed_fallback})"
        return fallback
    color = f"Color({hex_literal})"
    if apply_opacity and style.opacity is not None and 0.0 < style.opacity < 1.0:
        return f"{color}.withOpacity({round(style.opacity, 3)})"
    return color


def gradient_fill_expr(gradient: GradientFill) -> str | None:
    """Build a Dart LinearGradient or RadialGradient expression from Figma fills."""
    if not gradient.stops:
        return None

    stops = gradient.stops
    colors = ", ".join(f"Color({_argb_hex_literal(stop.color)})" for stop in stops)
    stop_positions = ", ".join(str(stop.position) for stop in stops)
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
