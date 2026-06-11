"""Text style helper expressions."""

from __future__ import annotations

from figma_flutter_agent.fonts.registry import load_font_registry
from figma_flutter_agent.generator.layout.style.colors import dart_color_expr
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
)
from figma_flutter_agent.parser.text_line_height import (
    flutter_text_style_height_ratio,
    leading_above_flutter_line_box,
)
from figma_flutter_agent.schemas import NodeStyle

_STRUT_LEADING_EPSILON = 0.5

def should_emit_strut_style(style: NodeStyle) -> bool:
    """Return True when Figma line-box metrics warrant ``StrutStyle`` (FID-42)."""
    if style.font_size is None or style.font_size <= 0:
        return False
    return (
        style.line_height is not None
        or style.glyph_top_offset is not None
        or style.glyph_height is not None
    )


def strut_style_expr(style: NodeStyle, *, omit_leading: bool = False) -> str | None:
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
    if (
        not omit_leading
        and style.glyph_top_offset is not None
        and style.glyph_top_offset > 0
        and style.font_size is not None
        and style.font_size > 0
    ):
        leading_above = leading_above_flutter_line_box(style.font_size, height_ratio)
        delta = style.glyph_top_offset - leading_above
        if delta > _STRUT_LEADING_EPSILON:
            parts.append(f"leading: {format_geometry_literal(delta)}")
    if not parts:
        return None
    return f"StrutStyle({', '.join(parts)})"


def wrap_tight_chip_label(widget: str, *, align: str = "Alignment.center") -> str:
    """Scale chip copy down inside a fixed pill instead of ellipsis truncation."""
    return f"FittedBox(fit: BoxFit.scaleDown, alignment: {align}, child: {widget})"


def text_widget_trailing_params(
    style: NodeStyle,
    *,
    text_align_suffix: str = "",
    include_text_scaler: bool = True,
    soft_wrap: bool | None = None,
    clip_single_line: bool = False,
    omit_strut: bool = False,
    optical_center: bool = False,
) -> str:
    """Build trailing ``Text`` constructor params (scaler, strut, align)."""
    parts: list[str] = []
    if include_text_scaler:
        parts.append("textScaler: textScaler")
    strut = None if omit_strut else strut_style_expr(style)
    if strut is not None:
        parts.append(f"strutStyle: {strut}")
    if optical_center:
        parts.append(
            "textHeightBehavior: const TextHeightBehavior("
            "applyHeightToFirstAscent: false, "
            "applyHeightToLastDescent: false)"
        )
    if soft_wrap is not None:
        parts.append(f"softWrap: {'true' if soft_wrap else 'false'}")
    if clip_single_line:
        parts.append("maxLines: 1")
        parts.append("overflow: TextOverflow.ellipsis")
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
    omit_line_height_for_strut: bool = False,
    omit_line_height: bool = False,
) -> list[str]:
    """Build ``copyWith`` deltas for theme-backed text (no inline font family)."""
    color = dart_color_expr(style, css_key=css_key, fallback=fallback)
    parts = [f"color: {color}"]
    # Pin explicit Figma glyph size; TextTheme slot metrics rarely match runtime Theme.
    emit_font_size = style.font_size is not None
    emit_font_weight = True
    if (
        style.font_weight
        and reference_font_weight
        and style.font_weight == reference_font_weight
    ):
        token = int(style.font_weight.removeprefix("w"))
        emit_font_weight = token >= 600
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
        skip_height = (
            omit_line_height
            or (omit_line_height_for_strut and should_emit_strut_style(style))
        )
        if height_ratio is not None and not skip_height:
            parts.append(f"height: {format_micro_style_literal(height_ratio)}")
            if height_ratio >= 1.15:
                parts.append("leadingDistribution: TextLeadingDistribution.proportional")
    if style.font_style == "italic":
        parts.append("fontStyle: FontStyle.italic")
    if style.text_decoration == "lineThrough":
        parts.append("decoration: TextDecoration.lineThrough")
    elif style.text_decoration == "underline":
        parts.append("decoration: TextDecoration.underline")
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
    omit_line_height_for_strut: bool = False,
    omit_line_height: bool = False,
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
        omit_line_height_for_strut=omit_line_height_for_strut,
        omit_line_height=omit_line_height,
    )
    if variant_font_size_expr is not None and not theme_token_matched:
        deltas.append(f"fontSize: {variant_font_size_expr}")
    base = f"Theme.of(context).textTheme.{slot}"
    if not deltas:
        return base
    return f"{base}?.copyWith({', '.join(deltas)})"
