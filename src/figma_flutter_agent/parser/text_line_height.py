"""Figma line-height normalization for Flutter ``TextStyle.height``."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_micro_style


def resolve_line_height(
    text_style: dict[str, Any],
    *,
    font_size: float | None,
) -> float | None:
    """Map Figma line height to Flutter ``TextStyle.height`` (unitless ratio)."""
    if font_size is None or font_size <= 0:
        return None
    size = float(font_size)
    line_height_px = text_style.get("lineHeightPx")
    if line_height_px is not None:
        return round_micro_style(float(line_height_px) / size)
    raw_line_height = text_style.get("lineHeight")
    if isinstance(raw_line_height, dict):
        unit = str(raw_line_height.get("unit") or "").upper()
        value = raw_line_height.get("value")
        if value is None:
            return None
        numeric = float(value)
        if unit in {"PIXELS", "PIXEL"}:
            return round_micro_style(numeric / size)
        if unit in {"FONT_SIZE_%", "FONT_SIZE_PERCENT", "PERCENT"}:
            return round_micro_style(numeric / 100.0)
        if numeric > 4.0:
            return round_micro_style(numeric / size)
        return round_micro_style(numeric)
    if isinstance(raw_line_height, (int, float)):
        numeric = float(raw_line_height)
        if numeric > 4.0:
            return round_micro_style(numeric / size)
        return round_micro_style(numeric)
    percent = text_style.get("lineHeightPercentFontSize")
    if percent is not None:
        return round_micro_style(float(percent) / 100.0)
    percent_raw = text_style.get("lineHeightPercent")
    if percent_raw is not None:
        return round_micro_style(float(percent_raw) / 100.0)
    return None


def flutter_text_style_height_ratio(
    line_height: float | None,
    *,
    font_size: float | None,
) -> float | None:
    """Return unitless ``TextStyle.height`` (``figmaLineHeight / figmaFontSize``)."""
    if line_height is None:
        return None
    if font_size is None or font_size <= 0:
        return line_height
    if line_height > 4.0 and line_height > font_size * 0.95:
        return round_micro_style(line_height / font_size)
    return line_height


def leading_above_flutter_line_box(
    font_size: float,
    line_height_ratio: float | None,
) -> float:
    """Estimate Flutter's default ascent padding above the glyph (FID-42 strut delta)."""
    if line_height_ratio is None or line_height_ratio <= 0:
        return 0.0
    line_box = font_size * line_height_ratio
    metric_glyph = font_size * 0.72
    return max(0.0, (line_box - metric_glyph) * 0.5)
