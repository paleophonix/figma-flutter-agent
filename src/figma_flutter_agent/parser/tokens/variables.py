"""Design-token extraction from Figma Variables API payloads."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.parser.tokens.colors import rgba_to_argb_hex
from figma_flutter_agent.parser.tokens.naming import allocate_token_name, sanitize_token_name
from figma_flutter_agent.schemas import DesignTokens


def merge_variable_payloads(
    local: dict[str, Any] | None,
    published: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Merge local and published Figma Variables API payloads."""
    if not local and not published:
        return None
    if not local:
        return published
    if not published:
        return local
    merged: dict[str, Any] = dict(local)
    merged_meta = dict(merged.get("meta") or {})
    local_vars = dict(merged_meta.get("variables") or {})
    published_vars = (published.get("meta") or {}).get("variables") or {}
    if isinstance(published_vars, dict):
        for variable_id, variable in published_vars.items():
            local_vars.setdefault(variable_id, variable)
    merged_meta["variables"] = local_vars
    merged["meta"] = merged_meta
    return merged


def resolve_image_fill_ref(image_ref: str, image_fill_urls: dict[str, str] | None) -> str | None:
    """Resolve a Figma ``imageRef`` to a download URL when the file images map is available."""
    if not image_ref or not image_fill_urls:
        return None
    return image_fill_urls.get(image_ref)


def extract_from_variables(payload: dict[str, Any] | None) -> DesignTokens | None:
    """Extract design tokens from the Variables API payload."""
    if not payload:
        return None

    colors: dict[str, str] = {}
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
            colors[name] = rgba_to_argb_hex(raw)

    spacing: dict[str, float] = {}
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
            rounded = round_geometry(float(raw))
            spacing[name] = rounded if rounded is not None else 0.0

    if not colors and not spacing:
        return None

    return DesignTokens(colors=colors, typography={}, spacing=spacing)
