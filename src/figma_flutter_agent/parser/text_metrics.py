"""Hydrate text metric frames from parsed Figma style data."""

from __future__ import annotations

from figma_flutter_agent.schemas import NodeStyle, NodeType, TextMetricsFrame


def hydrate_text_metrics_frame(
    node_type: NodeType,
    style: NodeStyle,
) -> TextMetricsFrame | None:
    """Build text metrics frame for TEXT nodes when line-box data exists."""
    if node_type != NodeType.TEXT:
        return None
    if (
        style.line_height is None
        and style.glyph_top_offset is None
        and style.glyph_height is None
    ):
        return None
    line_height_px = None
    if (
        style.line_height is not None
        and style.font_size is not None
        and style.font_size > 0
    ):
        line_height_px = style.line_height * style.font_size
    return TextMetricsFrame(
        line_height_px=line_height_px,
        glyph_top_offset=style.glyph_top_offset,
        glyph_height=style.glyph_height,
        font_size=style.font_size,
        strut_height_ratio=style.line_height,
        baseline_verifiable=style.font_size is not None and style.font_size > 0,
    )
