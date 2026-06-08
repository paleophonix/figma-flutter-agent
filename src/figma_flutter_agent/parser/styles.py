"""Figma node style enrichment."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.css import build_css_properties
from figma_flutter_agent.parser.effects import (
    derive_elevation,
    extract_blur_effects,
    extract_gradient_fill,
    extract_shadow_effects,
    parse_corner_radii,
)
from figma_flutter_agent.parser.numeric_rounding import round_micro_style
from figma_flutter_agent.parser.style_refs import resolve_style_name, style_reference_paints
from figma_flutter_agent.parser.text_line_height import resolve_line_height
from figma_flutter_agent.parser.tokens.colors import rgba_to_argb_hex
from figma_flutter_agent.parser.typography import (
    resolve_font_family,
    resolve_font_style,
    resolve_font_weight,
    resolve_letter_spacing,
)
from figma_flutter_agent.schemas import NodeStyle

_INVISIBLE_PAINT_OPACITY = 0.01


def enrich_node_style(
    node: dict[str, Any],
    style: NodeStyle,
    *,
    published_styles: dict[str, dict[str, Any]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
    dev_mode_css: dict[str, str] | None = None,
    dev_mode_css_override: bool = False,
) -> NodeStyle:
    """Apply extended style extraction and CSS properties to a node style."""
    style_source = style_reference_paints(node, style_paint_index) or node
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
        _enrich_text_style(style_source, node, fills, style)

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

    corner_radii = parse_corner_radii(node)
    if corner_radii is not None:
        style.border_radius_corners = corner_radii
    elif style.border_radius is None:
        corner = node.get("cornerRadius")
        if corner is not None:
            style.border_radius = round_micro_style(float(corner))

    _enrich_stroke_style(node, strokes, style)

    style_name = resolve_style_name(node, published_styles)
    if style_name:
        style.style_name = style_name

    if str(node.get("type") or "").upper() != "TEXT":
        _enrich_render_bounds_expand(node, style)

    raw_blend = node.get("blendMode")
    if raw_blend and raw_blend not in ("NORMAL", "PASS_THROUGH"):
        style.blend_mode = raw_blend

    style.css_properties = build_css_properties(style)

    if dev_mode_css:
        from figma_flutter_agent.parser.dev_mode_css import merge_dev_mode_css_into_style

        style.css_properties = merge_dev_mode_css_into_style(
            style.css_properties,
            dev_mode_css,
            override=dev_mode_css_override,
        )

    return style


def _enrich_text_style(
    style_source: dict[str, Any],
    node: dict[str, Any],
    fills: list[dict[str, Any]],
    style: NodeStyle,
) -> None:
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


def _enrich_stroke_style(
    node: dict[str, Any],
    strokes: list[dict[str, Any]],
    style: NodeStyle,
) -> None:
    stroke_align = node.get("strokeAlign")
    if stroke_align is not None:
        style.stroke_align = str(stroke_align)
    dash = node.get("strokeDashes") or node.get("dashPattern")
    if isinstance(dash, list) and dash:
        style.stroke_dash_pattern = [float(value) for value in dash]

    for stroke in strokes:
        if not _stroke_is_visible(stroke):
            continue
        style.has_stroke = True
        if stroke.get("color"):
            style.border_color = rgba_to_argb_hex(stroke["color"])
        if node.get("strokeWeight") is not None:
            style.border_width = float(node["strokeWeight"])
        break


def _stroke_is_visible(stroke: dict[str, Any]) -> bool:
    """Return True when a Figma SOLID stroke should affect emitted borders."""
    if stroke.get("visible") is False or stroke.get("type") != "SOLID":
        return False
    opacity = stroke.get("opacity")
    if opacity is not None and float(opacity) <= _INVISIBLE_PAINT_OPACITY:
        return False
    color = stroke.get("color") or {}
    alpha = color.get("a")
    return alpha is None or float(alpha) > _INVISIBLE_PAINT_OPACITY


def _enrich_render_bounds_expand(node: dict[str, Any], style: NodeStyle) -> None:
    from figma_flutter_agent.parser.render_bounds import (
        compute_render_bounds_expand,
        compute_style_outward_expand_fallback,
    )

    bbox = node.get("absoluteBoundingBox") or {}
    render = node.get("absoluteRenderBounds") or {}
    expand = compute_render_bounds_expand(bbox, render)
    if expand is None:
        expand = compute_style_outward_expand_fallback(style)
    if expand is not None:
        style.render_bounds_expand = expand
