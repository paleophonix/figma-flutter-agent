"""Figma style, effect, and CSS-like property extraction."""

from __future__ import annotations

import math
from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_geometry, round_micro_style
from figma_flutter_agent.parser.text_line_height import resolve_line_height
from figma_flutter_agent.parser.tokens import rgba_to_argb_hex
from figma_flutter_agent.parser.typography import (
    resolve_font_family,
    resolve_font_style,
    resolve_font_weight,
    resolve_letter_spacing,
)
from figma_flutter_agent.schemas import (
    CornerRadii,
    GradientFill,
    GradientStop,
    NodeStyle,
    ShadowEffect,
)


def argb_hex_to_css_rgba(hex_value: str) -> str:
    """Convert Flutter ARGB hex to CSS rgba() string."""
    normalized = hex_value.removeprefix("0x").removeprefix("0X")
    if len(normalized) != 8:
        return hex_value
    alpha = int(normalized[0:2], 16) / 255
    red = int(normalized[2:4], 16)
    green = int(normalized[4:6], 16)
    blue = int(normalized[6:8], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.3f})"


def extract_layer_blur(node: dict[str, Any]) -> float | None:
    """Extract visible layer blur radius from Figma effects."""
    layer, _ = extract_blur_effects(node)
    return layer


def extract_blur_effects(node: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract ``LAYER_BLUR`` and ``BACKGROUND_BLUR`` radii separately (FID-41).

    Args:
        node: Raw Figma node dict (or effects-bearing style source).

    Returns:
        Tuple of ``(layer_blur, background_blur)``; either may be ``None``.
    """
    layer_blur: float | None = None
    background_blur: float | None = None
    for effect in node.get("effects") or []:
        if effect.get("visible") is False:
            continue
        effect_type = effect.get("type")
        radius = effect.get("radius")
        if radius is None:
            continue
        value = float(radius)
        if effect_type == "LAYER_BLUR":
            layer_blur = value
        elif effect_type == "BACKGROUND_BLUR":
            background_blur = value
    return layer_blur, background_blur


def _parse_corner_radii(node: dict[str, Any]) -> CornerRadii | None:
    raw = node.get("rectangleCornerRadii")
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        values = [round_micro_style(float(value)) or 0.0 for value in raw]
    except (TypeError, ValueError):
        return None
    return CornerRadii(
        top_left=values[0],
        top_right=values[1],
        bottom_right=values[2],
        bottom_left=values[3],
    )


def extract_shadow_effects(node: dict[str, Any]) -> list[ShadowEffect]:
    """Extract visible drop and inner shadows from a Figma node."""
    effects: list[ShadowEffect] = []
    for effect in node.get("effects") or []:
        if effect.get("visible") is False:
            continue
        effect_type = effect.get("type")
        if effect_type not in {"DROP_SHADOW", "INNER_SHADOW"}:
            continue
        color_payload = effect.get("color") or {}
        effects.append(
            ShadowEffect(
                kind="inner" if effect_type == "INNER_SHADOW" else "drop",
                offset_x=round_geometry(float(effect.get("offset", {}).get("x", 0))) or 0.0,
                offset_y=round_geometry(float(effect.get("offset", {}).get("y", 0))) or 0.0,
                blur=float(effect.get("radius", 0)),
                spread=float(effect.get("spread", 0)),
                color=rgba_to_argb_hex(color_payload),
            )
        )
    return effects


def extract_gradient_fill(fills: list[dict[str, Any]]) -> GradientFill | None:
    """Extract the first visible gradient fill from Figma fills."""
    for fill in fills:
        if fill.get("visible") is False:
            continue
        fill_type = fill.get("type")
        if fill_type == "GRADIENT_LINEAR":
            stops = [
                GradientStop(
                    position=float(stop.get("position", 0)),
                    color=rgba_to_argb_hex(stop.get("color") or {}),
                )
                for stop in fill.get("gradientStops") or []
            ]
            angle = _linear_gradient_angle(fill.get("gradientHandlePositions") or [])
            return GradientFill(type="linear", stops=stops, angle=angle)
        if fill_type == "GRADIENT_RADIAL":
            stops = [
                GradientStop(
                    position=float(stop.get("position", 0)),
                    color=rgba_to_argb_hex(stop.get("color") or {}),
                )
                for stop in fill.get("gradientStops") or []
            ]
            return GradientFill(type="radial", stops=stops)
    return None


def _linear_gradient_angle(handles: list[dict[str, float]]) -> float | None:
    if len(handles) < 2:
        return None
    start = handles[0]
    end = handles[1]
    delta_x = end.get("x", 0) - start.get("x", 0)
    delta_y = end.get("y", 0) - start.get("y", 0)
    if delta_x == 0 and delta_y == 0:
        return None
    return round(math.degrees(math.atan2(delta_y, delta_x)), 2)


def derive_elevation(effects: list[ShadowEffect]) -> float | None:
    """Derive a Material-like elevation value from drop shadows."""
    drop_blurs = [effect.blur for effect in effects if effect.kind == "drop"]
    if not drop_blurs:
        return None
    return round(max(drop_blurs) / 4, 2)


def resolve_style_name(
    node: dict[str, Any],
    published_styles: dict[str, dict[str, Any]] | None,
) -> str | None:
    """Resolve a published Figma style name referenced by the node."""
    if not published_styles:
        return None
    style_refs = node.get("styles") or {}
    for style_id in style_refs.values():
        style_meta = published_styles.get(style_id)
        if style_meta and style_meta.get("name"):
            return str(style_meta["name"])
    return None


def collect_style_node_ids(published_styles: dict[str, dict[str, Any]]) -> list[str]:
    """Collect style definition node ids from published style metadata."""
    node_ids: list[str] = []
    seen: set[str] = set()
    for style_meta in published_styles.values():
        node_id = style_meta.get("node_id")
        if not node_id or node_id in seen:
            continue
        seen.add(str(node_id))
        node_ids.append(str(node_id))
    return node_ids


def build_style_paint_index(
    published_styles: dict[str, dict[str, Any]],
    style_nodes: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Map published style ids to their style definition node documents."""
    index: dict[str, dict[str, Any]] = {}
    for style_id, style_meta in published_styles.items():
        node_id = style_meta.get("node_id")
        if not node_id:
            continue
        style_node = style_nodes.get(str(node_id))
        if style_node is not None:
            index[style_id] = style_node
    return index


def _style_reference_paints(
    node: dict[str, Any],
    style_paint_index: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Resolve published style paints referenced by a node."""
    if not style_paint_index:
        return None
    style_refs = node.get("styles") or {}
    for style_key in ("fill", "text", "stroke", "effect"):
        style_id = style_refs.get(style_key)
        if not style_id:
            continue
        style_node = style_paint_index.get(style_id)
        if style_node is not None:
            return style_node
    return None


# Figma blendMode → CSS mix-blend-mode (NORMAL/PASS_THROUGH omitted — browser default)
_FIGMA_BLEND_TO_CSS: dict[str, str] = {
    "MULTIPLY": "multiply",
    "SCREEN": "screen",
    "OVERLAY": "overlay",
    "DARKEN": "darken",
    "LIGHTEN": "lighten",
    "COLOR_DODGE": "color-dodge",
    "COLOR_BURN": "color-burn",
    "HARD_LIGHT": "hard-light",
    "SOFT_LIGHT": "soft-light",
    "DIFFERENCE": "difference",
    "EXCLUSION": "exclusion",
    "HUE": "hue",
    "SATURATION": "saturation",
    "COLOR": "color",
    "LUMINOSITY": "luminosity",
}

# Figma textAlignHorizontal → CSS text-align
_FIGMA_TEXT_ALIGN_TO_CSS: dict[str, str] = {
    "LEFT": "left",
    "RIGHT": "right",
    "CENTER": "center",
    "JUSTIFIED": "justify",
}


def build_css_properties(style: NodeStyle) -> dict[str, str]:
    """Build a complete CSS-like property dict from REST-synthesised NodeStyle fields.

    Covers every visual attribute the Figma REST API exposes — equivalent to
    what the Figma Inspect panel shows via ``getCSSAsync()``, without requiring
    a Dev Mode seat or plugin.
    """
    css: dict[str, str] = {}

    # Colour / background
    if style.background_color:
        css["background-color"] = argb_hex_to_css_rgba(style.background_color)
    if style.text_color:
        css["color"] = argb_hex_to_css_rgba(style.text_color)

    # Shape
    if style.border_radius is not None:
        css["border-radius"] = f"{style.border_radius:g}px"
    if style.border_width is not None:
        css["border-width"] = f"{style.border_width:g}px"
    if style.border_color:
        css["border-color"] = argb_hex_to_css_rgba(style.border_color)

    # Typography
    if style.font_size is not None:
        css["font-size"] = f"{style.font_size:g}px"
    if style.font_weight:
        css["font-weight"] = style.font_weight.removeprefix("w")
    if style.font_family:
        css["font-family"] = style.font_family
    if style.font_style and style.font_style.lower() != "normal":
        css["font-style"] = style.font_style.lower()
    if style.text_align:
        css_align = _FIGMA_TEXT_ALIGN_TO_CSS.get(style.text_align.upper(), style.text_align.lower())
        css["text-align"] = css_align
    if style.line_height is not None:
        css["line-height"] = f"{style.line_height:g}"
    if style.letter_spacing is not None:
        css["letter-spacing"] = f"{style.letter_spacing:g}px"

    # Visibility / compositing
    if style.opacity is not None:
        css["opacity"] = str(style.opacity)
    if style.blend_mode:
        css_blend = _FIGMA_BLEND_TO_CSS.get(style.blend_mode)
        if css_blend:
            css["mix-blend-mode"] = css_blend
    if style.layer_blur is not None:
        css["filter"] = f"blur({style.layer_blur:g}px)"

    # Elevation (non-standard, kept for downstream consumers)
    if style.elevation is not None:
        css["elevation"] = str(style.elevation)

    # Gradient background
    if style.gradient:
        stop_values = ", ".join(
            f"{argb_hex_to_css_rgba(stop.color)} {int(stop.position * 100)}%"
            for stop in style.gradient.stops
        )
        if style.gradient.type == "linear":
            angle = style.gradient.angle if style.gradient.angle is not None else 180
            css["background"] = f"linear-gradient({angle}deg, {stop_values})"
        else:
            css["background"] = f"radial-gradient(circle, {stop_values})"

    # Shadows
    if style.effects:
        shadow_values = []
        for effect in style.effects:
            inset = "inset " if effect.kind == "inner" else ""
            shadow_values.append(
                f"{inset}{effect.offset_x}px {effect.offset_y}px {effect.blur}px "
                f"{effect.spread}px {argb_hex_to_css_rgba(effect.color)}"
            )
        css["box-shadow"] = ", ".join(shadow_values)

    return css


def enrich_node_style(
    node: dict[str, Any],
    style: NodeStyle,
    *,
    published_styles: dict[str, dict[str, Any]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
    dev_mode_css: dict[str, str] | None = None,
    dev_mode_css_override: bool = False,
) -> NodeStyle:
    """Apply extended style extraction and CSS properties to a node style.

    Args:
        node: Raw Figma node dict.
        style: NodeStyle to enrich in-place (mutated).
        published_styles: Published style metadata index.
        style_paint_index: Style paint index for style references.
        dev_mode_css: Optional CSS-property dict from a Dev Mode dump
            (loaded by :mod:`figma_flutter_agent.parser.dev_mode_css`).
            When provided, these properties are merged into
            ``style.css_properties`` after REST synthesis.
        dev_mode_css_override: When ``True``, dump values win over
            REST-synthesised ones (used in ``dev_mode_inspect`` source mode).
    """
    style_source = _style_reference_paints(node, style_paint_index) or node
    fills = style_source.get("fills") or node.get("fills") or []
    strokes = style_source.get("strokes") or node.get("strokes") or []

    if style.background_color is None and node.get("type") != "TEXT":
        for fill in fills:
            if fill.get("visible") is False:
                continue
            if fill.get("type") == "SOLID" and fill.get("color"):
                style.background_color = rgba_to_argb_hex(fill["color"])
                break

    if node.get("type") == "TEXT" and style.text_color is None:
        text_style = style_source.get("style") or node.get("style") or {}
        if text_style.get("fontSize") is not None and style.font_size is None:
            style.font_size = float(text_style["fontSize"])
        if style.font_weight is None:
            resolved_weight = resolve_font_weight(text_style)
            if resolved_weight is not None:
                style.font_weight = resolved_weight
        if style.font_family is None:
            resolved_family = resolve_font_family(text_style)
            if resolved_family is not None:
                style.font_family = resolved_family
        if style.font_style is None:
            resolved_style = resolve_font_style(text_style)
            if resolved_style is not None:
                style.font_style = resolved_style
        if style.letter_spacing is None:
            resolved_spacing = resolve_letter_spacing(text_style, font_size=style.font_size)
            if resolved_spacing is not None:
                style.letter_spacing = resolved_spacing
        if style.line_height is None:
            resolved_line_height = resolve_line_height(text_style, font_size=style.font_size)
            if resolved_line_height is not None:
                style.line_height = resolved_line_height
        for fill in fills:
            if fill.get("visible") is False:
                continue
            if fill.get("type") == "SOLID" and fill.get("color"):
                style.text_color = rgba_to_argb_hex(fill["color"])
                break

    gradient = extract_gradient_fill(fills)
    if gradient is not None:
        style.gradient = gradient

    effects_source = node if node.get("effects") else style_source
    effects = extract_shadow_effects(effects_source)
    if effects:
        style.effects = effects
        style.elevation = derive_elevation(effects)

    layer_blur, background_blur = extract_blur_effects(effects_source)
    if layer_blur is not None and layer_blur > 0:
        style.layer_blur = layer_blur
    if background_blur is not None and background_blur > 0:
        style.background_blur = background_blur

    if node.get("opacity") is not None:
        style.opacity = round_micro_style(float(node["opacity"]))

    corner_radii = _parse_corner_radii(node)
    if corner_radii is not None:
        style.border_radius_corners = corner_radii
    elif style.border_radius is None:
        corner = node.get("cornerRadius")
        if corner is not None:
            style.border_radius = round_micro_style(float(corner))

    stroke_align = node.get("strokeAlign")
    if stroke_align is not None:
        style.stroke_align = str(stroke_align)
    dash = node.get("strokeDashes") or node.get("dashPattern")
    if isinstance(dash, list) and dash:
        style.stroke_dash_pattern = [float(value) for value in dash]

    for stroke in strokes:
        if stroke.get("visible") is False or stroke.get("type") != "SOLID":
            continue
        style.has_stroke = True
        if stroke.get("color"):
            style.border_color = rgba_to_argb_hex(stroke["color"])
        if node.get("strokeWeight") is not None:
            style.border_width = float(node["strokeWeight"])
        break

    style_name = resolve_style_name(node, published_styles)
    if style_name:
        style.style_name = style_name

    if str(node.get("type") or "").upper() != "TEXT":
        from figma_flutter_agent.parser.render_bounds import compute_render_bounds_expand

        bbox = node.get("absoluteBoundingBox") or {}
        render = node.get("absoluteRenderBounds") or {}
        expand = compute_render_bounds_expand(bbox, render)
        if expand is not None:
            style.render_bounds_expand = expand

    # blend_mode from Figma blendMode field
    raw_blend = node.get("blendMode")
    if raw_blend and raw_blend not in ("NORMAL", "PASS_THROUGH"):
        style.blend_mode = raw_blend

    # Always build CSS from REST-synthesised fields (replaces manual inspection).
    style.css_properties = build_css_properties(style)

    # Optionally merge Dev Mode dump CSS on top (plugin dump enrichment).
    # In hybrid mode dump fills gaps; in dev_mode_inspect dump overrides.
    if dev_mode_css:
        from figma_flutter_agent.parser.dev_mode_css import merge_dev_mode_css_into_style

        style.css_properties = merge_dev_mode_css_into_style(
            style.css_properties,
            dev_mode_css,
            override=dev_mode_css_override,
        )

    return style
