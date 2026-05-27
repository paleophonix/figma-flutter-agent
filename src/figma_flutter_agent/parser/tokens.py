"""Design token extraction from Figma payloads."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from loguru import logger

from figma_flutter_agent.schemas import (
    ColorToken,
    DesignTokens,
    ElevationToken,
    RadiusToken,
    SpacingToken,
    TypographyToken,
)

_NAME_SANITIZER = re.compile(r"[^a-zA-Z0-9]+")
_NEUTRAL_THRESHOLD = 0.05
_DEFAULT_PRIMARY = "0xFF6750A4"

_DART_KEYWORDS = frozenset(
    {
        "abstract",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "covariant",
        "default",
        "deferred",
        "do",
        "dynamic",
        "else",
        "enum",
        "export",
        "extends",
        "extension",
        "external",
        "factory",
        "false",
        "final",
        "finally",
        "for",
        "Function",
        "get",
        "hide",
        "if",
        "implements",
        "import",
        "in",
        "interface",
        "is",
        "late",
        "library",
        "mixin",
        "new",
        "null",
        "on",
        "operator",
        "part",
        "required",
        "rethrow",
        "return",
        "sealed",
        "set",
        "show",
        "static",
        "super",
        "switch",
        "sync",
        "this",
        "throw",
        "true",
        "try",
        "typedef",
        "var",
        "void",
        "when",
        "while",
        "with",
        "yield",
    }
)


def _normalize_dart_identifier(name: str) -> str:
    if not name:
        return "tToken"
    if name[0].isdigit() or name in _DART_KEYWORDS:
        return f"t{name[0].upper()}{name[1:]}"
    return name


def sanitize_token_name(name: str) -> str:
    """Convert a Figma style name to a Dart-safe camelCase token name."""
    parts = [part for part in _NAME_SANITIZER.split(name) if part]
    if not parts:
        return "tToken"
    head, *tail = parts
    candidate = head.lower() + "".join(part.capitalize() for part in tail)
    return _normalize_dart_identifier(candidate)


def allocate_token_name(base: str, used: set[str]) -> str:
    """Return a unique Dart token name, suffixing with ``2``, ``3``, … on collision."""
    if base not in used:
        used.add(base)
        return base
    index = 2
    while True:
        candidate = f"{base}{index}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def rgba_to_argb_hex(color: dict[str, float]) -> str:
    """Convert Figma RGBA (0-1 floats) to Flutter ARGB hex string."""
    alpha = int(round((color.get("a", 1.0)) * 255))
    red = int(round(color.get("r", 0) * 255))
    green = int(round(color.get("g", 0) * 255))
    blue = int(round(color.get("b", 0) * 255))
    return f"0x{alpha:02X}{red:02X}{green:02X}{blue:02X}"


def is_neutral_rgba(color: dict[str, float]) -> bool:
    """Return True when a color is near white or near black."""
    red = color.get("r", 0.0)
    green = color.get("g", 0.0)
    blue = color.get("b", 0.0)
    if (
        red > 1 - _NEUTRAL_THRESHOLD
        and green > 1 - _NEUTRAL_THRESHOLD
        and blue > 1 - _NEUTRAL_THRESHOLD
    ):
        return True
    return red < _NEUTRAL_THRESHOLD and green < _NEUTRAL_THRESHOLD and blue < _NEUTRAL_THRESHOLD


def select_primary_color_hex(color_counts: Counter[str], neutral_hexes: set[str]) -> str | None:
    """Pick the most frequent non-neutral fill color for the primary token."""
    for hex_value, _count in color_counts.most_common():
        if hex_value not in neutral_hexes:
            return hex_value
    return None


def build_color_tokens(color_counts: Counter[str], neutral_hexes: set[str]) -> list[ColorToken]:
    """Build color tokens with a frequency-based primary seed color."""
    primary_hex = select_primary_color_hex(color_counts, neutral_hexes)
    if primary_hex is None:
        if color_counts:
            logger.warning(
                "Only neutral colors (near white/black) were found in fills; "
                "using default Material seed color for primary."
            )
        return [ColorToken(name="primary", value=_DEFAULT_PRIMARY)]

    used_names = {"primary"}
    tokens: list[ColorToken] = [ColorToken(name="primary", value=primary_hex)]
    seen_hex = {primary_hex}

    for hex_value, _count in color_counts.most_common():
        if hex_value in seen_hex:
            continue
        token_name = allocate_token_name(f"color{len(tokens)}", used_names)
        tokens.append(ColorToken(name=token_name, value=hex_value))
        seen_hex.add(hex_value)

    return tokens


def extract_from_variables(payload: dict[str, Any] | None) -> DesignTokens | None:
    """Extract design tokens from the Variables API payload."""
    if not payload:
        return None

    colors: list[ColorToken] = []
    used_color_names: set[str] = set()
    meta = payload.get("meta", {})
    variables = meta.get("variables", {})

    for variable_id, variable in variables.items():
        if variable.get("resolvedType") != "COLOR":
            continue
        base_name = sanitize_token_name(variable.get("name", variable_id))
        name = allocate_token_name(base_name, used_color_names)
        mode_values = variable.get("valuesByMode") or {}
        if not mode_values:
            continue
        raw = next(iter(mode_values.values()))
        if isinstance(raw, dict) and "r" in raw:
            colors.append(ColorToken(name=name, value=rgba_to_argb_hex(raw)))

    spacing: list[SpacingToken] = []
    used_spacing_names: set[str] = set()
    for variable_id, variable in variables.items():
        if variable.get("resolvedType") != "FLOAT":
            continue
        base_name = sanitize_token_name(variable.get("name", variable_id))
        name = allocate_token_name(base_name, used_spacing_names)
        mode_values = variable.get("valuesByMode") or {}
        if not mode_values:
            continue
        raw = next(iter(mode_values.values()))
        if isinstance(raw, (int, float)):
            spacing.append(SpacingToken(name=name, value=float(raw)))

    if not colors and not spacing:
        return None

    return DesignTokens(colors=colors, typography=[], spacing=spacing)


def _walk_nodes(
    node: dict[str, Any],
    color_counts: Counter[str],
    neutral_hexes: set[str],
    typography: dict[str, TypographyToken],
    used_typography_names: set[str],
    spacing_values: set[float],
    radius_values: set[float],
    elevation_values: set[float],
) -> None:
    item_spacing = node.get("itemSpacing")
    if isinstance(item_spacing, (int, float)):
        spacing_values.add(float(item_spacing))

    corner_radius = node.get("cornerRadius")
    if isinstance(corner_radius, (int, float)) and corner_radius > 0:
        radius_values.add(float(corner_radius))

    for effect in node.get("effects") or []:
        if effect.get("visible") is False:
            continue
        if effect.get("type") != "DROP_SHADOW":
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
            base_name = sanitize_token_name(node.get("name", "bodyMedium"))
            style_name = allocate_token_name(base_name, used_typography_names)
            typography[style_name] = TypographyToken(
                style_name=style_name,
                font_size=float(font_size),
                font_weight=f"w{int(style.get('fontWeight', 400))}",
            )

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
        )


def extract_from_tree(root: dict[str, Any]) -> DesignTokens:
    """Fallback token extraction from fills and text styles in the node tree."""
    color_counts: Counter[str] = Counter()
    neutral_hexes: set[str] = set()
    typography: dict[str, TypographyToken] = {}
    used_typography_names: set[str] = set()
    spacing_values: set[float] = set()
    radius_values: set[float] = set()
    elevation_values: set[float] = set()
    _walk_nodes(
        root,
        color_counts,
        neutral_hexes,
        typography,
        used_typography_names,
        spacing_values,
        radius_values,
        elevation_values,
    )

    color_tokens = build_color_tokens(color_counts, neutral_hexes)

    spacing_tokens = [
        SpacingToken(name="md" if index == 0 else f"space{index}", value=value)
        for index, value in enumerate(sorted(spacing_values))
    ] or [SpacingToken(name="md", value=16.0)]

    used_radius_names: set[str] = set()
    radius_tokens = [
        RadiusToken(
            name=allocate_token_name("md" if index == 0 else f"radius{index}", used_radius_names),
            value=value,
        )
        for index, value in enumerate(sorted(radius_values))
    ] or [RadiusToken(name="md", value=8.0)]

    used_elevation_names: set[str] = set()
    elevation_tokens = [
        ElevationToken(
            name=allocate_token_name(
                "md" if index == 0 else f"elevation{index}", used_elevation_names
            ),
            value=value,
        )
        for index, value in enumerate(sorted(elevation_values))
    ] or [ElevationToken(name="md", value=4.0)]

    return DesignTokens(
        colors=color_tokens,
        typography=list(typography.values())
        or [TypographyToken(style_name="titleLarge", font_size=22, font_weight="w400")],
        spacing=spacing_tokens,
        radii=radius_tokens,
        elevations=elevation_tokens,
    )


def build_design_tokens(
    root: dict[str, Any],
    variables_payload: dict[str, Any] | None,
) -> DesignTokens:
    """Build design tokens using variables first, then tree fallback."""
    from_variables = extract_from_variables(variables_payload)
    if from_variables and from_variables.colors:
        tree_tokens = extract_from_tree(root)
        if not from_variables.typography:
            from_variables.typography = tree_tokens.typography
        if not from_variables.spacing:
            from_variables.spacing = tree_tokens.spacing
        return from_variables
    return extract_from_tree(root)
