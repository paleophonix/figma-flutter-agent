"""Import design tokens from external JSON token files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.parser.tokens.naming import allocate_token_name, sanitize_token_name
from figma_flutter_agent.schemas import DesignTokens, Padding, TypographyStyle


def import_design_tokens_json(path: Path) -> DesignTokens:
    """Import design tokens from a W3C / Figma Tokens plugin JSON export."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    colors: dict[str, str] = {}
    spacing: dict[str, float] = {}
    radii: dict[str, float] = {}
    typography: dict[str, TypographyStyle] = {}
    edge_insets: dict[str, Padding] = {}
    icons: dict[str, str] = {}
    used_names: set[str] = set()

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            if value.get("$type") == "color" and "$value" in value:
                name = allocate_token_name(sanitize_token_name(prefix), used_names)
                colors[name] = str(value["$value"])
                return
            if value.get("$type") in {"dimension", "number"} and "$value" in value:
                name = allocate_token_name(sanitize_token_name(prefix), used_names)
                numeric = float(str(value["$value"]).replace("px", "").strip())
                spacing[name] = numeric
                return
            for key, child in value.items():
                if key.startswith("$"):
                    continue
                child_prefix = f"{prefix}/{key}" if prefix else key
                walk(child_prefix, child)
            return
        if isinstance(value, str) and prefix:
            name = allocate_token_name(sanitize_token_name(prefix), used_names)
            if value.startswith("#") or value.startswith("0x"):
                colors[name] = value if value.startswith("0x") else f"0xFF{value[1:]}"
            else:
                spacing[name] = float(value.replace("px", "").strip())

    if isinstance(raw, dict):
        walk("", raw)
    return DesignTokens(
        colors=colors,
        typography=typography or {"bodyMedium": TypographyStyle(font_size=14, font_weight="w400")},
        spacing=spacing or {"md": 16.0},
        radii=radii or {"md": 8.0},
        edge_insets=edge_insets,
        icons=icons,
    )
