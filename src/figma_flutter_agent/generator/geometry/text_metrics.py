"""Text metric adjustments for geometry planning."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.baseline import flutter_baseline_offset
from figma_flutter_agent.schemas import TextMetricsFrame

_BASELINE_EPSILON = 0.5


def leading_above_flutter(
    font_size: float,
    line_height_ratio: float | None,
    *,
    font_family: str | None = None,
) -> float:
    if line_height_ratio is None or line_height_ratio <= 0:
        return 0.0
    line_box = font_size * line_height_ratio
    metric_glyph = flutter_baseline_offset(font_size, font_family=font_family)
    return max(0.0, (line_box - metric_glyph) * 0.5)


def compute_delta_top(metrics: TextMetricsFrame) -> float | None:
    if metrics.glyph_top_offset is None or metrics.font_size is None:
        return None
    leading = leading_above_flutter(metrics.font_size, metrics.strut_height_ratio)
    delta = metrics.glyph_top_offset - leading
    if abs(delta) <= _BASELINE_EPSILON:
        return None
    return delta
