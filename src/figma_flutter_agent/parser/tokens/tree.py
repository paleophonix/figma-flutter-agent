"""Fallback design-token extraction from a Figma node tree."""

from __future__ import annotations

from collections import Counter
from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.parser.tokens.colors import (
    build_color_tokens,
    is_neutral_rgba,
    rgba_to_argb_hex,
)
from figma_flutter_agent.parser.tokens.naming import allocate_token_name, sanitize_token_name
from figma_flutter_agent.schemas import DesignTokens, Padding, TypographyStyle


def _padding_from_node(node: dict[str, Any]) -> Padding | None:
    """Extract padding when any side is set on a Figma node."""
    top = node.get("paddingTop")
    bottom = node.get("paddingBottom")
    left = node.get("paddingLeft")
    right = node.get("paddingRight")
    if not any(isinstance(value, (int, float)) for value in (top, bottom, left, right)):
        return None
    return Padding(
        top=float(top or 0),
        bottom=float(bottom or 0),
        left=float(left or 0),
        right=float(right or 0),
    )


def _walk_nodes(
    node: dict[str, Any],
    color_counts: Counter[str],
    neutral_hexes: set[str],
    typography: dict[str, TypographyStyle],
    used_typography_names: set[str],
    spacing_values: set[float],
    radius_values: set[float],
    elevation_values: set[float],
    padding_values: set[tuple[float, float, float, float]],
    icon_asset_keys: dict[str, str],
    used_icon_names: set[str],
) -> None:
    item_spacing = node.get("itemSpacing")
    if isinstance(item_spacing, (int, float)):
        rounded = round_geometry(float(item_spacing))
        spacing_values.add(rounded if rounded is not None else 0.0)

    corner_radius = node.get("cornerRadius")
    if isinstance(corner_radius, (int, float)) and corner_radius > 0:
        radius_values.add(float(corner_radius))

    for effect in node.get("effects") or []:
        if effect.get("visible") is False or effect.get("type") != "DROP_SHADOW":
            continue
        shadow_radius = effect.get("radius")
        if isinstance(shadow_radius, (int, float)) and shadow_radius >= 0:
            elevation_values.add(float(shadow_radius))

    for fill in node.get("fills") or []:
        if fill.get("visible") is False or fill.get("type") != "SOLID":
            continue
        color = fill.get("color")
        if not color:
            continue
        hex_value = rgba_to_argb_hex(color)
        color_counts[hex_value] += 1
        if is_neutral_rgba(color):
            neutral_hexes.add(hex_value)

    if node.get("type") == "TEXT":
        style = node.get("style") or {}
        font_size = style.get("fontSize")
        if font_size:
            from figma_flutter_agent.parser.typography import resolve_font_weight

            base_name = sanitize_token_name(node.get("name", "bodyMedium"))
            style_name = allocate_token_name(base_name, used_typography_names)
            typography[style_name] = TypographyStyle(
                font_size=float(font_size),
                font_weight=resolve_font_weight(style) or "w400",
            )

    padding = _padding_from_node(node)
    if padding is not None:
        padding_values.add((padding.top, padding.bottom, padding.left, padding.right))

    if node.get("type") == "RECTANGLE" and node.get("name"):
        for fill in node.get("fills") or []:
            if fill.get("type") == "IMAGE" and fill.get("visible", True) is not False:
                base_name = sanitize_token_name(str(node.get("name", "icon")))
                token_name = allocate_token_name(base_name, used_icon_names)
                icon_asset_keys.setdefault(token_name, token_name)
                break

    for child in node.get("children") or []:
        _walk_nodes(
            child,
            color_counts,
            neutral_hexes,
            typography,
            used_typography_names,
            spacing_values,
            radius_values,
            elevation_values,
            padding_values,
            icon_asset_keys,
            used_icon_names,
        )


def extract_from_tree(root: dict[str, Any]) -> DesignTokens:
    """Fallback token extraction from fills and text styles in the node tree."""
    color_counts: Counter[str] = Counter()
    neutral_hexes: set[str] = set()
    typography: dict[str, TypographyStyle] = {}
    used_typography_names: set[str] = set()
    spacing_values: set[float] = set()
    radius_values: set[float] = set()
    elevation_values: set[float] = set()
    padding_values: set[tuple[float, float, float, float]] = set()
    icon_asset_keys: dict[str, str] = {}
    used_icon_names: set[str] = set()
    _walk_nodes(
        root,
        color_counts,
        neutral_hexes,
        typography,
        used_typography_names,
        spacing_values,
        radius_values,
        elevation_values,
        padding_values,
        icon_asset_keys,
        used_icon_names,
    )

    color_tokens = build_color_tokens(color_counts, neutral_hexes)

    used_spacing_names: set[str] = set()
    spacing_tokens = {
        allocate_token_name("md" if index == 0 else f"space{index}", used_spacing_names): (
            round_geometry(value) or 0.0
        )
        for index, value in enumerate(sorted(spacing_values))
    }
    if not spacing_tokens:
        spacing_tokens = {"md": 16.0}

    used_radius_names: set[str] = set()
    radius_tokens = {
        allocate_token_name("md" if index == 0 else f"radius{index}", used_radius_names): value
        for index, value in enumerate(sorted(radius_values))
    }
    if not radius_tokens:
        radius_tokens = {"md": 8.0}

    used_elevation_names: set[str] = set()
    elevation_tokens = {
        allocate_token_name("md" if index == 0 else f"elevation{index}", used_elevation_names): value
        for index, value in enumerate(sorted(elevation_values))
    }
    if not elevation_tokens:
        elevation_tokens = {"md": 4.0}

    if not typography:
        typography = {"titleLarge": TypographyStyle(font_size=22, font_weight="w400")}

    used_inset_names: set[str] = set()
    edge_inset_tokens: dict[str, Padding] = {}
    for index, (top, bottom, left, right) in enumerate(sorted(padding_values)):
        name = allocate_token_name("md" if index == 0 else f"inset{index}", used_inset_names)
        edge_inset_tokens[name] = Padding(top=top, bottom=bottom, left=left, right=right)

    return DesignTokens(
        colors=color_tokens,
        typography=typography,
        spacing=spacing_tokens,
        radii=radius_tokens,
        elevations=elevation_tokens,
        edge_insets=edge_inset_tokens,
        icons=dict(icon_asset_keys),
    )


def merge_token_maps(base: DesignTokens, fallback: DesignTokens) -> DesignTokens:
    """Fill empty token maps on ``base`` from ``fallback``."""
    updates: dict[str, object] = {}
    if not base.typography:
        updates["typography"] = fallback.typography
    if not base.spacing:
        updates["spacing"] = fallback.spacing
    if not base.radii:
        updates["radii"] = fallback.radii
    if not base.elevations:
        updates["elevations"] = fallback.elevations
    if not base.edge_insets:
        updates["edge_insets"] = fallback.edge_insets
    if not base.icons:
        updates["icons"] = fallback.icons
    if not updates:
        return base
    return base.model_copy(update=updates)
