"""Rich text span extraction from Figma style overrides."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.interaction import is_link_text
from figma_flutter_agent.parser.tokens.colors import solid_paint_to_argb_hex
from figma_flutter_agent.parser.typography import resolve_font_weight
from figma_flutter_agent.schemas import TextSpanPart


def resolve_uniform_text_override_color(node: dict[str, Any]) -> str | None:
    """Return SOLID fill color when every character shares one non-base override style.

    Args:
        node: Raw Figma TEXT node dictionary.

    Returns:
        ARGB hex when a uniform ``characterStyleOverrides`` entry supplies a fill color.
    """
    if node.get("type") != "TEXT":
        return None
    characters = str(node.get("characters") or "")
    overrides = node.get("characterStyleOverrides")
    if not isinstance(overrides, list) or len(overrides) != len(characters):
        return None
    if len(set(overrides)) != 1:
        return None
    style_id = overrides[0]
    if not style_id:
        return None
    override = (node.get("styleOverrideTable") or {}).get(str(style_id), {})
    for fill in override.get("fills") or []:
        if fill.get("type") == "SOLID" and fill.get("color"):
            return solid_paint_to_argb_hex(
                fill["color"],
                paint_opacity=float(fill.get("opacity", 1.0)),
            )
    return None


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
                text_color = solid_paint_to_argb_hex(
                    fill["color"],
                    paint_opacity=float(fill.get("opacity", 1.0)),
                )
                break
        override_style = override.get("style") or {}
        merged_style = {**base_style, **override_style}
        font_weight = resolve_font_weight(merged_style)
        letter_spacing = merged_style.get("letterSpacing")
        text_decoration = None
        if merged_style.get("textDecoration") == "UNDERLINE":
            text_decoration = "underline"
        elif merged_style.get("textDecoration") == "STRIKETHROUGH":
            text_decoration = "lineThrough"
        spans.append(
            TextSpanPart(
                text=chunk,
                text_color=text_color,
                font_weight=font_weight,
                is_link=is_link_text(chunk),
                letter_spacing=float(letter_spacing) if letter_spacing is not None else None,
                text_decoration=text_decoration,
            )
        )
    return collapse_adjacent_text_spans(spans) if spans else None


def collapse_adjacent_text_spans(spans: list[TextSpanPart]) -> list[TextSpanPart]:
    """Merge adjacent spans with identical style (FID-09 run collapse)."""
    if len(spans) < 2:
        return spans
    merged: list[TextSpanPart] = []
    for span in spans:
        if not merged:
            merged.append(span)
            continue
        prev = merged[-1]
        if (
            prev.text_color == span.text_color
            and prev.font_weight == span.font_weight
            and prev.letter_spacing == span.letter_spacing
            and prev.text_decoration == span.text_decoration
            and prev.is_link == span.is_link
            and not prev.is_link
        ):
            merged[-1] = TextSpanPart(
                text=prev.text + span.text,
                text_color=prev.text_color,
                font_weight=prev.font_weight,
                is_link=prev.is_link,
                letter_spacing=prev.letter_spacing,
                text_decoration=prev.text_decoration,
            )
        else:
            merged.append(span)
    cleaned: list[TextSpanPart] = []
    for span in merged:
        text = span.text.replace("\n", " ") if span.is_link else span.text
        cleaned.append(span.model_copy(update={"text": text}))
    return cleaned
