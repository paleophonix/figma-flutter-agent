"""Map clean-tree styles to Dart theme expressions for deterministic codegen."""

from __future__ import annotations

import math
import re

from figma_flutter_agent.fonts.registry import load_font_registry
from figma_flutter_agent.generator.theme_typography import (
    metrics_for_text_theme_slot,
    resolve_text_theme_slot,
)
from figma_flutter_agent.schemas import DesignTokens
from figma_flutter_agent.generator.variant_props import (
    variant_font_size,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
)
from figma_flutter_agent.generator.render_units import (
    format_figma_blur_radius_literal,
    figma_spread_to_flutter_spread,
)
from figma_flutter_agent.parser.text_line_height import flutter_text_style_height_ratio
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GradientFill,
    NodeStyle,
    NodeType,
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
        fields.append(f"borderRadius: {border_radius_expr(style)}")
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
        if (style.stroke_align or "").upper() != "OUTSIDE":
            fields.append(f"border: Border.all(color: {border_color}, width: {border_width})")
    if style.effects:
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
    radius = style.border_radius
    fields = [f"border: Border.all(color: {border_color}, width: {border_width})"]
    if radius is not None:
        fields.append(f"borderRadius: {border_radius_expr(style)}")
    return f"BoxDecoration({', '.join(fields)})"


def should_emit_strut_style(style: NodeStyle) -> bool:
    """Return True when Figma line-box metrics warrant ``StrutStyle`` (FID-42)."""
    if style.font_size is None or style.font_size <= 0:
        return False
    if style.line_height is not None:
        return True
    if style.glyph_top_offset is not None:
        return True
    if style.glyph_height is not None:
        return True
    return False


def strut_style_expr(style: NodeStyle) -> str | None:
    """Build ``StrutStyle(...)`` pinning the Figma line box (FID-42)."""
    if not should_emit_strut_style(style):
        return None
    parts: list[str] = []
    if style.font_size is not None:
        parts.append(f"fontSize: {format_micro_style_literal(style.font_size)}")
    height_ratio = flutter_text_style_height_ratio(
        style.line_height,
        font_size=style.font_size,
    )
    if height_ratio is not None:
        parts.append(f"height: {format_micro_style_literal(height_ratio)}")
        parts.append("forceStrutHeight: true")
    if style.glyph_top_offset is not None and style.glyph_top_offset > 0:
        parts.append(f"leading: {format_geometry_literal(style.glyph_top_offset)}")
    if not parts:
        return None
    return f"StrutStyle({', '.join(parts)})"


def text_widget_trailing_params(
    style: NodeStyle,
    *,
    text_align_suffix: str = "",
    include_text_scaler: bool = True,
) -> str:
    """Build trailing ``Text`` constructor params (scaler, strut, align)."""
    parts: list[str] = []
    if include_text_scaler:
        parts.append("textScaler: textScaler")
    strut = strut_style_expr(style)
    if strut is not None:
        parts.append(f"strutStyle: {strut}")
    align = text_align_suffix.strip()
    if align.startswith(","):
        align = align.removeprefix(",").strip()
    if align:
        parts.append(align)
    return ", ".join(parts)


def card_elevation_expr(style: NodeStyle) -> str:
    """Build a Dart elevation expression for Material cards."""
    if style.elevation is not None:
        return str(style.elevation)
    return "AppElevation.md"


def border_radius_expr(style: NodeStyle) -> str:
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


def _text_style_delta_fields(
    style: NodeStyle,
    *,
    css_key: str = "color",
    fallback: str = "AppColors.primary",
    theme_token_matched: bool,
    text_theme_slot: str | None = None,
    reference_font_size: float | None = None,
    reference_font_weight: str | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    """Build ``copyWith`` deltas for theme-backed text (no inline font family)."""
    color = dart_color_expr(style, css_key=css_key, fallback=fallback)
    parts = [f"color: {color}"]
    emit_font_size = style.font_size is not None
    if emit_font_size and reference_font_size is not None:
        emit_font_size = abs(float(style.font_size) - float(reference_font_size)) > 0.5
    emit_font_weight = True
    if (
        style.font_weight
        and reference_font_weight
        and style.font_weight == reference_font_weight
    ):
        emit_font_weight = False
    if not theme_token_matched or emit_font_size or emit_font_weight:
        if emit_font_size and style.font_size is not None:
            parts.append(f"fontSize: {style.font_size}")
        if emit_font_weight:
            weight_expr = _flutter_font_weight_expr(
                style,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            )
            if weight_expr is not None:
                parts.append(f"fontWeight: {weight_expr}")
        height_ratio = flutter_text_style_height_ratio(
            style.line_height,
            font_size=style.font_size,
        )
        if height_ratio is not None and not should_emit_strut_style(style):
            parts.append(f"height: {format_micro_style_literal(height_ratio)}")
            if height_ratio >= 1.15:
                parts.append("leadingDistribution: TextLeadingDistribution.proportional")
    if style.font_style == "italic":
        parts.append("fontStyle: FontStyle.italic")
    if style.letter_spacing is not None:
        spacing = float(style.letter_spacing)
        if style.font_size is not None and style.font_size > 0:
            spacing = min(spacing, float(style.font_size) * 0.12)
        parts.append(f"letterSpacing: {format_micro_style_literal(spacing)}")
    return parts


def _theme_text_style_expr(
    style: NodeStyle,
    *,
    slot: str,
    theme_token_matched: bool,
    reference_font_size: float | None = None,
    reference_font_weight: str | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    variant_font_size_expr: str | None = None,
) -> str:
    """Build ``Theme.of(context).textTheme.<slot>`` with optional ``copyWith`` deltas."""
    deltas = _text_style_delta_fields(
        style,
        theme_token_matched=theme_token_matched,
        text_theme_slot=slot,
        reference_font_size=reference_font_size,
        reference_font_weight=reference_font_weight,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
    )
    if variant_font_size_expr is not None and not theme_token_matched:
        deltas.append(f"fontSize: {variant_font_size_expr}")
    base = f"Theme.of(context).textTheme.{slot}"
    if not deltas:
        return base
    return f"{base}?.copyWith({', '.join(deltas)})"


def filled_button_label_text_color(
    node: CleanDesignTreeNode,
    parent: CleanDesignTreeNode,
) -> str | None:
    """Return ``Color(0xFFFFFFFF)`` when *node* is the primary label of a filled button.

    A text node is considered a primary label when:
    1. Its parent stack contains at least one CONTAINER sibling with a non-None
       ``background_color`` (the button fill).
    2. The text node is in the top half of the parent stack (its vertical
       centre ≤ ``parent.sizing.height / 2``).

    Args:
        node: A TEXT node to test.
        parent: Parent STACK node.

    Returns:
        ``"Color(0xFFFFFFFF)"`` for primary labels; ``None`` otherwise.
    """
    if node.type != NodeType.TEXT:
        return None
    if parent.type == NodeType.BUTTON:
        if parent.style.background_color is None:
            return None
        first_text = next(
            (child for child in parent.children if child.type == NodeType.TEXT),
            None,
        )
        if first_text is None or first_text.id != node.id:
            return None
        return "Color(0xFFFFFFFF)"
    if parent.type != NodeType.STACK:
        return None
    has_fill = any(
        child.type == NodeType.CONTAINER and child.style.background_color is not None
        for child in parent.children
    )
    if not has_fill:
        return None
    # Only the primary (first) TEXT child of a filled stack gets forced-white label colour.
    # Secondary labels and footers that follow it are intentionally not overridden.
    first_text = next(
        (child for child in parent.children if child.type == NodeType.TEXT), None
    )
    if first_text is None or first_text.id != node.id:
        return None
    return "Color(0xFFFFFFFF)"


def text_style_expr(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    design_tokens: DesignTokens | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
) -> str:
    """Build a theme-backed text style expression for a clean-tree text node."""
    style = node.style
    if parent_node is not None:
        label_color = filled_button_label_text_color(node, parent_node)
        if label_color is not None and style.text_color is None:
            style = style.model_copy(update={"text_color": "0xFFFFFFFF"})
    slot_map = text_theme_slot_by_style_name or {}
    size_slots = text_theme_size_slots or []
    slot, theme_matched = resolve_text_theme_slot(
        style,
        slot_by_style_name=slot_map,
        size_slots=size_slots,
    )
    ref_size, ref_weight = metrics_for_text_theme_slot(
        slot,
        size_slots,
        design_tokens,
    )
    variant_size = variant_font_size(node) if style.font_size is None else None
    return _theme_text_style_expr(
        style,
        slot=slot,
        theme_token_matched=theme_matched,
        reference_font_size=ref_size,
        reference_font_weight=ref_weight,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        variant_font_size_expr=variant_size,
    )


def text_span_style_expr(
    part: TextSpanPart,
    base_style: NodeStyle,
    *,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
) -> str:
    """Build a theme-backed style expression for one rich-text span."""
    style = NodeStyle(
        text_color=part.text_color or base_style.text_color,
        font_size=base_style.font_size,
        font_weight=part.font_weight or base_style.font_weight,
        line_height=base_style.line_height,
        letter_spacing=base_style.letter_spacing,
        font_family=base_style.font_family,
        font_style=base_style.font_style,
        style_name=base_style.style_name,
    )
    slot_map = text_theme_slot_by_style_name or {}
    size_slots = text_theme_size_slots or []
    slot, theme_matched = resolve_text_theme_slot(
        style,
        slot_by_style_name=slot_map,
        size_slots=size_slots,
    )
    return _theme_text_style_expr(
        style,
        slot=slot,
        theme_token_matched=theme_matched,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
    )


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
