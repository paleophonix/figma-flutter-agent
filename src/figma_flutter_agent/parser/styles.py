"""Figma style, effect, and CSS-like property extraction."""

from __future__ import annotations

import math
from typing import Any

from figma_flutter_agent.parser.tokens import rgba_to_argb_hex
from figma_flutter_agent.parser.numeric_rounding import round_geometry, round_micro_style
from figma_flutter_agent.parser.typography import (
    resolve_font_family,
    resolve_font_style,
    resolve_font_weight,
    resolve_letter_spacing,
)
from figma_flutter_agent.parser.text_line_height import resolve_line_height
from figma_flutter_agent.schemas import GradientFill, GradientStop, NodeStyle, ShadowEffect


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
    for effect in node.get("effects") or []:
        if effect.get("visible") is False:
            continue
        if effect.get("type") == "LAYER_BLUR":
            radius = effect.get("radius")
            if radius is not None:
                return float(radius)
    return None


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


def build_css_properties(style: NodeStyle) -> dict[str, str]:
    """Build CSS-like properties from extracted node style metadata."""
    css: dict[str, str] = {}
    if style.background_color:
        css["background-color"] = argb_hex_to_css_rgba(style.background_color)
    if style.text_color:
        css["color"] = argb_hex_to_css_rgba(style.text_color)
    if style.border_radius is not None:
        css["border-radius"] = f"{style.border_radius}px"
    if style.border_width is not None:
        css["border-width"] = f"{style.border_width}px"
    if style.border_color:
        css["border-color"] = argb_hex_to_css_rgba(style.border_color)
    if style.font_size is not None:
        css["font-size"] = f"{style.font_size}px"
    if style.font_weight:
        css["font-weight"] = style.font_weight.removeprefix("w")
    if style.opacity is not None:
        css["opacity"] = str(style.opacity)
    if style.elevation is not None:
        css["elevation"] = str(style.elevation)
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
) -> NodeStyle:
    """Apply extended style extraction and CSS properties to a node style."""
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

    layer_blur = extract_layer_blur(effects_source)
    if layer_blur is not None and layer_blur > 0:
        style.layer_blur = layer_blur

    if node.get("opacity") is not None:
        style.opacity = round_micro_style(float(node["opacity"]))

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

    return style
