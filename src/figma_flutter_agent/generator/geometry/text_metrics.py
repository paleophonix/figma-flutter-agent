"""Text metric adjustments for geometry planning."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.baseline import flutter_baseline_offset
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    StackPlacement,
    TextMetricsFrame,
)

_BASELINE_EPSILON = 0.5
_SPACING_SLACK_FRACTION = 0.25
_POSITIONED_TEXT_WIDTH_METRIC_SLACK = 1.12
_POSITIONED_TEXT_MIN_EXTRA_WIDTH = 4.0


def should_skip_centered_glyph_delta(node: CleanDesignTreeNode) -> bool:
    """Return True when short centered glyph text must not receive delta-top correction."""
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


def placement_is_fill_width_centered_text(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> bool:
    """Return True when text fills a dual-inset slot with centered alignment."""
    if node.type != NodeType.TEXT:
        return False
    if (node.style.text_align or "").upper() != "CENTER":
        return False
    horizontal = (placement.horizontal or "").upper()
    if horizontal != "LEFT_RIGHT":
        return False
    return placement.left is not None and placement.right is not None


def placement_is_center_pinned_horizontal(placement: StackPlacement) -> bool:
    """Return True when a stack child is horizontally centered with dual insets."""
    return (
        (placement.horizontal or "").upper() == "CENTER"
        and placement.left is not None
        and placement.right is not None
        and float(placement.left) > 1.5
        and float(placement.right) > 1.5
    )


def positioned_text_allows_metric_slack(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> bool:
    """Return True when absolute TEXT may widen its positioned slot for glyph bounds."""
    if node.type != NodeType.TEXT:
        return False
    if placement_is_fill_width_centered_text(node, placement):
        return False
    return not placement_is_center_pinned_horizontal(placement)


def center_pinned_text_explicit_lane_width(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
    *,
    parent_width: float | None,
) -> float | None:
    """Widen center-pinned text lanes when the Figma box underfits measured copy."""
    if node.type != NodeType.TEXT:
        return None
    if not placement_is_center_pinned_horizontal(placement):
        return None
    if parent_width is None or parent_width <= 0:
        return None
    from figma_flutter_agent.generator.dart.llm_codegen.text_copy import _estimated_text_width

    estimated = _estimated_text_width(node)
    if estimated is None:
        return None
    lane_width = placement.width
    if lane_width is None and placement.left is not None and placement.right is not None:
        lane_width = float(parent_width) - float(placement.left) - float(placement.right)
    if lane_width is None or estimated <= float(lane_width) + 1.5:
        return None
    return min(estimated, float(parent_width) - 4.0)


def positioned_text_width_with_metric_slack(figma_width: float) -> float:
    """Widen absolute text slots so Flutter font metrics do not clip trailing glyphs."""
    scaled = float(figma_width) * _POSITIONED_TEXT_WIDTH_METRIC_SLACK
    slack_width = max(scaled, float(figma_width) + _POSITIONED_TEXT_MIN_EXTRA_WIDTH)
    if slack_width == int(slack_width):
        return float(int(slack_width))
    return round(slack_width, 1)


def placement_is_right_edge_pinned(
    placement: StackPlacement,
    *,
    parent_width: float | None,
    figma_width: float,
) -> bool:
    """Return True when text ends flush with the parent right edge."""
    if parent_width is None or placement.left is None:
        return False
    right_edge = float(placement.left) + float(figma_width)
    return abs(right_edge - float(parent_width)) <= 2.0


def positioned_text_preserves_right_edge(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
    *,
    parent_width: float | None,
    figma_width: float,
) -> bool:
    """Return True when metric slack must preserve the original right anchor."""
    if node.type != NodeType.TEXT:
        return False
    if (node.style.text_align or "").upper() == "RIGHT":
        return placement_is_right_edge_pinned(
            placement,
            parent_width=parent_width,
            figma_width=figma_width,
        )
    return placement_is_right_edge_pinned(
        placement,
        parent_width=parent_width,
        figma_width=figma_width,
    )


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
