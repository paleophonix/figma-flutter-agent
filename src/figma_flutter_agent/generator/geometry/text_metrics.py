"""Text metric adjustments for geometry planning."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.baseline import flutter_baseline_offset
from figma_flutter_agent.schemas import CleanDesignTreeNode, TextMetricsFrame

_BASELINE_EPSILON = 0.5
_SPACING_SLACK_FRACTION = 0.25


def should_skip_centered_glyph_delta(node: CleanDesignTreeNode) -> bool:
    """Return True when short centered glyph text must not receive delta-top correction."""
    from figma_flutter_agent.schemas import NodeType

    glyph = (node.text or "").strip()
    return (
        node.type == NodeType.TEXT
        and (node.style.text_align or "").upper() == "CENTER"
        and 0 < len(glyph) <= 3
    )


def text_uses_delta_top_layout_wrap(node: CleanDesignTreeNode) -> bool:
    """Return True when geometry planner applies ``DELTA_TOP_PADDING`` for this node."""
    from figma_flutter_agent.schemas import WrapKind

    slot = node.layout_slot
    return slot is not None and WrapKind.DELTA_TOP_PADDING in slot.wraps


def strut_leading_ratio(
    font_size: float,
    glyph_top_offset: float,
    line_height_ratio: float | None,
    *,
    font_family: str | None = None,
) -> float | None:
    """Return ``StrutStyle.leading`` as a unitless font-size multiplier (FID-42)."""
    leading = leading_above_flutter(font_size, line_height_ratio, font_family=font_family)
    delta = glyph_top_offset - leading
    if delta <= _BASELINE_EPSILON:
        return None
    return delta / font_size


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


def predict_typography_slack(node: CleanDesignTreeNode) -> float:
    """Conservative extra vertical slack for Flutter strut vs Figma bbox drift."""
    metrics = node.text_metrics_frame
    if metrics is None:
        return 0.0
    slack = 0.0
    if metrics.line_height_px is not None and metrics.glyph_height is not None:
        slack += max(0.0, float(metrics.line_height_px) - float(metrics.glyph_height))
    if metrics.delta_top is not None:
        slack += abs(float(metrics.delta_top))
    if (node.spacing or 0.0) > 0.0:
        slack += float(node.spacing) * _SPACING_SLACK_FRACTION
    return slack


def compute_delta_top(metrics: TextMetricsFrame) -> float | None:
    if metrics.glyph_top_offset is None or metrics.font_size is None:
        return None
    leading = leading_above_flutter(metrics.font_size, metrics.strut_height_ratio)
    delta = metrics.glyph_top_offset - leading
    if abs(delta) <= _BASELINE_EPSILON:
        return None
    return delta
