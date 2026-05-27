"""Rich text span extraction from Figma style overrides."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.interaction import is_link_text
from figma_flutter_agent.parser.tokens import rgba_to_argb_hex
from figma_flutter_agent.parser.typography import resolve_font_weight
from figma_flutter_agent.schemas import TextSpanPart


def extract_text_span_parts(node: dict[str, Any]) -> list[TextSpanPart] | None:
    """Build text span parts when ``characterStyleOverrides`` vary within one TEXT node.

    Args:
        node: Raw Figma TEXT node dictionary.

    Returns:
        Span list when multiple styles are present; otherwise ``None``.
    """
    if node.get("type") != "TEXT":
        return None
    characters = str(node.get("characters") or "")
    if not characters:
        return None
    overrides = node.get("characterStyleOverrides")
    if not isinstance(overrides, list) or len(overrides) != len(characters):
        return None
    if len(set(overrides)) <= 1:
        return None

    table = node.get("styleOverrideTable") or {}
    base_style = node.get("style") or {}
    spans: list[TextSpanPart] = []
    index = 0
    while index < len(characters):
        style_id = overrides[index]
        start = index
        while index < len(characters) and overrides[index] == style_id:
            index += 1
        chunk = characters[start:index]
        if not chunk:
            continue
        override = table.get(str(style_id), {}) if style_id else {}
        text_color: str | None = None
        for fill in override.get("fills") or []:
            if fill.get("type") == "SOLID" and fill.get("color"):
                text_color = rgba_to_argb_hex(fill["color"])
                break
        override_style = override.get("style") or {}
        merged_style = {**base_style, **override_style}
        font_weight = resolve_font_weight(merged_style)
        spans.append(
            TextSpanPart(
                text=chunk,
                text_color=text_color,
                font_weight=font_weight,
                is_link=is_link_text(chunk),
            )
        )
    return spans or None
