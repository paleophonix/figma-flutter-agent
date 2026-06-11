"""Per-node inference helpers for clean tree conversion."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.components import (
    infer_semantic_type_from_figma_overlay,
    resolve_semantic_node_type,
)
from figma_flutter_agent.parser.dev_mode_css import DevModeCssDump
from figma_flutter_agent.parser.geometry import (
    rotation_degrees_from_figma_node,
    rotation_radians_from_figma_node,
)
from figma_flutter_agent.parser.numeric_rounding import round_geometry, round_micro_style
from figma_flutter_agent.parser.styles import enrich_node_style
from figma_flutter_agent.parser.tokens.colors import rgba_to_argb_hex
from figma_flutter_agent.parser.typography import (
    resolve_font_family,
    resolve_font_style,
    resolve_font_weight,
    resolve_letter_spacing,
)
from figma_flutter_agent.schemas import NodeStyle, NodeType


def figma_layout_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return a node view for layout inference (spec section 7.1)."""
    if node.get("type") == "SECTION":
        return {**node, "type": "FRAME"}
    return node


def infer_leaf_type(
    node: dict[str, Any],
    *,
    components: dict[str, dict[str, Any]] | None = None,
    component_sets: dict[str, dict[str, Any]] | None = None,
) -> NodeType:
    node_type = node.get("type")
    name = (node.get("name") or "").lower()
    if node_type == "TEXT":
        return NodeType.TEXT
    if node_type in {"VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "ELLIPSE", "POLYGON"}:
        if any(fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])):
            return NodeType.IMAGE
        return NodeType.VECTOR

    semantic_type = resolve_semantic_node_type(node, components, component_sets)
    if semantic_type is not None:
        return semantic_type

    overlay_type = infer_semantic_type_from_figma_overlay(node)
    if overlay_type is not None:
        return overlay_type
    if node_type == "RECTANGLE" and any(
        fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])
    ):
        return NodeType.IMAGE

    # Unpublished instances: avoid layer-name heuristics when Components API data exists.
    if node_type == "INSTANCE" and node.get("componentId") and components:
        return NodeType.CONTAINER

    if "input" in name:
        return NodeType.INPUT
    if "button" in name or (node_type == "INSTANCE" and "btn" in name):
        return NodeType.BUTTON
    if "card" in name:
        return NodeType.CARD
    return NodeType.CONTAINER


def leaf_type_used_name_hint(node: dict[str, Any], node_type: NodeType) -> bool:
    """Return True when ``infer_leaf_type`` assigned type via layer-name heuristics."""
    if node_type not in {NodeType.INPUT, NodeType.BUTTON, NodeType.CARD}:
        return False
    name = (node.get("name") or "").lower()
    node_type_raw = node.get("type")
    if "input" in name and node_type == NodeType.INPUT:
        return True
    if ("button" in name or (node_type_raw == "INSTANCE" and "btn" in name)) and node_type == NodeType.BUTTON:
        return True
    if "card" in name and node_type == NodeType.CARD:
        return True
    return False


def extract_style(
    node: dict[str, Any],
    *,
    published_styles: dict[str, dict[str, Any]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
    dev_mode_dump: DevModeCssDump | None = None,
    dev_mode_css_override: bool = False,
) -> NodeStyle:
    style = NodeStyle()
    fills = node.get("fills") or []
    if node.get("type") != "TEXT":
        for fill in fills:
            if fill.get("visible") is False:
                continue
            if fill.get("type") == "SOLID" and fill.get("color"):
                style.background_color = rgba_to_argb_hex(fill["color"])
                break

    if node.get("cornerRadius") is not None:
        style.border_radius = round_geometry(float(node["cornerRadius"]))

    if node.get("type") == "TEXT":
        text_style = node.get("style") or {}
        if text_style.get("fontSize") is not None:
            style.font_size = float(text_style["fontSize"])
        resolved_weight = resolve_font_weight(text_style)
        if resolved_weight is not None:
            style.font_weight = resolved_weight
        resolved_family = resolve_font_family(text_style)
        if resolved_family is not None:
            style.font_family = resolved_family
        resolved_style = resolve_font_style(text_style)
        if resolved_style is not None:
            style.font_style = resolved_style
        align = text_style.get("textAlignHorizontal")
        if isinstance(align, str) and align.strip():
            style.text_align = align.strip().upper()
        if text_style.get("fontSize") is not None and style.font_size is None:
            style.font_size = float(text_style["fontSize"])
        from figma_flutter_agent.parser.text_line_height import resolve_line_height

        resolved_line_height = resolve_line_height(text_style, font_size=style.font_size)
        if resolved_line_height is not None:
            style.line_height = resolved_line_height
        resolved_spacing = resolve_letter_spacing(text_style, font_size=style.font_size)
        if resolved_spacing is not None:
            style.letter_spacing = resolved_spacing
        decoration = text_style.get("textDecoration")
        if decoration == "UNDERLINE":
            style.text_decoration = "underline"
        elif decoration == "STRIKETHROUGH":
            style.text_decoration = "lineThrough"
        bbox = node.get("absoluteBoundingBox") or {}
        render = node.get("absoluteRenderBounds") or {}
        if bbox.get("y") is not None and render.get("y") is not None:
            style.glyph_top_offset = round_geometry(float(render["y"]) - float(bbox["y"]))
        if render.get("height") is not None:
            style.glyph_height = round_geometry(float(render["height"]))
        for fill in fills:
            if fill.get("visible") is False:
                continue
            if fill.get("type") == "SOLID" and fill.get("color"):
                style.text_color = rgba_to_argb_hex(fill["color"])
                break

    dev_mode_css: dict[str, str] | None = None
    if dev_mode_dump is not None:
        entry = dev_mode_dump.get_node(node["id"])
        if entry is not None:
            dev_mode_css = entry.css

    return enrich_node_style(
        node,
        style,
        published_styles=published_styles,
        style_paint_index=style_paint_index,
        dev_mode_css=dev_mode_css,
        dev_mode_css_override=dev_mode_css_override,
    )


def extract_rotation_degrees(node: dict[str, Any]) -> float | None:
    degrees = rotation_degrees_from_figma_node(node)
    if degrees is None:
        return None
    return round_micro_style(degrees)


def extract_rotation_rad(node: dict[str, Any]) -> float | None:
    radians = rotation_radians_from_figma_node(node)
    if radians is None:
        return None
    return round_micro_style(radians)
