"""Flex delta planning: FILL/HUG/FIXED semantics for geometry planner."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.baseline import flutter_baseline_offset
from figma_flutter_agent.generator.layout.flex_policy import FlexWrapKind, resolve_flex_wrap
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    SizingMode,
    TextMetricsFrame,
    WrapKind,
)

_MIN_TOUCH_HEIGHT = 48.0


def _leading_above_flutter(
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


def _flex_wrap_to_kind(kind: FlexWrapKind) -> WrapKind | None:
    if kind == FlexWrapKind.EXPANDED:
        return WrapKind.EXPANDED
    if kind == FlexWrapKind.FLEXIBLE_LOOSE:
        return WrapKind.FLEXIBLE_LOOSE
    if kind == FlexWrapKind.SIZED_BOX_WIDTH:
        return WrapKind.CONSTRAINED_BOX
    return None


def _wrap_for_fill(
    parent_type: NodeType,
    child: CleanDesignTreeNode,
) -> WrapKind | None:
    """Map FILL sizing to main-axis Expanded or cross-axis stretch (INV-FLEX-AXIS)."""
    width_fill = child.sizing.width_mode == SizingMode.FILL
    height_fill = child.sizing.height_mode == SizingMode.FILL
    if parent_type == NodeType.ROW:
        if width_fill:
            return WrapKind.EXPANDED
        if height_fill:
            return WrapKind.CROSS_STRETCH_HEIGHT
    elif parent_type == NodeType.COLUMN:
        if height_fill:
            return WrapKind.EXPANDED
        if width_fill:
            return WrapKind.CROSS_STRETCH_WIDTH
    return None


def _input_line_box_height(
    hint: CleanDesignTreeNode | None,
    *,
    font_size: float,
    line_height_ratio: float | None,
) -> float:
    """Return the Flutter line box height used to vertically center input copy."""
    if hint is not None and hint.text_metrics_frame is not None:
        line_height_px = hint.text_metrics_frame.line_height_px
        if line_height_px is not None and line_height_px > 0:
            return float(line_height_px)
    if line_height_ratio is not None and line_height_ratio > 0:
        return float(font_size) * float(line_height_ratio)
    return float(font_size)


def compute_input_metrics(node: CleanDesignTreeNode) -> TextMetricsFrame | None:
    """Compute INPUT vertical padding channel (single source for T3 on inputs)."""
    if node.type != NodeType.INPUT:
        return None
    frame_height = node.sizing.height
    if frame_height is None or frame_height <= 0:
        return None
    from figma_flutter_agent.parser.interaction import (
        input_hint_node,
        input_value_style_node,
    )

    hint = input_hint_node(node)
    value = input_value_style_node(node)
    style_source = value or hint
    font_size = style_source.style.font_size if style_source is not None else 14.0
    glyph_height = (
        style_source.style.glyph_height
        if style_source is not None and style_source.style.glyph_height
        else font_size
    )
    glyph_top = (
        style_source.style.glyph_top_offset
        if style_source is not None and style_source.style.glyph_top_offset is not None
        else 0.0
    )
    ratio = style_source.style.line_height if style_source is not None else None
    font_family = (
        style_source.style.font_family
        if style_source is not None
        else node.style.font_family
    )
    pad = node.padding
    if pad is not None and pad.top is not None and pad.bottom is not None:
        if pad.top > 0 and pad.bottom > 0:
            return TextMetricsFrame(
                font_size=float(font_size),
                glyph_height=float(glyph_height),
                glyph_top_offset=float(glyph_top),
                strut_height_ratio=ratio,
                input_padding_top=float(pad.top),
                input_padding_bottom=float(pad.bottom),
                delta_top=float(pad.top),
                baseline_verifiable=False,
            )
    line_box_height = _input_line_box_height(
        style_source,
        font_size=float(font_size),
        line_height_ratio=ratio,
    )
    leading = _leading_above_flutter(float(font_size), ratio, font_family=font_family)
    padding_top = max(0.0, float(glyph_top) - leading)
    padding_bottom = max(0.0, float(frame_height) - padding_top - line_box_height)
    return TextMetricsFrame(
        font_size=float(font_size),
        glyph_height=float(glyph_height),
        glyph_top_offset=float(glyph_top),
        strut_height_ratio=ratio,
        leading_above_flutter=leading,
        input_padding_top=padding_top,
        input_padding_bottom=padding_bottom,
        delta_top=padding_top,
        baseline_verifiable=False,
    )


def compute_flex_deltas(
    parent: CleanDesignTreeNode,
    child: CleanDesignTreeNode,
) -> tuple[tuple[WrapKind, ...], TextMetricsFrame | None]:
    """Return planner wraps and optional INPUT metrics for a flex child."""
    parent_type = parent.type
    if parent_type not in {NodeType.ROW, NodeType.COLUMN}:
        return (), None

    wraps: list[WrapKind] = []
    input_metrics: TextMetricsFrame | None = None

    if child.type == NodeType.INPUT:
        input_metrics = compute_input_metrics(child)
        fill_wrap = _wrap_for_fill(parent_type, child)
        if fill_wrap is not None:
            wraps.append(fill_wrap)
        return tuple(dict.fromkeys(wraps)), input_metrics

    fill_wrap = _wrap_for_fill(parent_type, child)
    if fill_wrap is not None:
        wraps.append(fill_wrap)

    kind = resolve_flex_wrap(parent_type=parent_type, node=child, parent_node=parent)
    mapped = _flex_wrap_to_kind(kind)
    if mapped is not None and mapped not in wraps:
        wraps.append(mapped)

    if (
        child.sizing.width_mode == SizingMode.FIXED
        and child.sizing.width
        and parent_type == NodeType.ROW
        and WrapKind.EXPANDED not in wraps
    ):
        wraps.append(WrapKind.CONSTRAINED_BOX)

    wraps_tuple = tuple(dict.fromkeys(wraps))
    if (
        parent_type == NodeType.ROW
        and child.sizing.width_mode == SizingMode.FIXED
        and WrapKind.CONSTRAINED_BOX in wraps_tuple
        and WrapKind.FLEXIBLE_LOOSE in wraps_tuple
    ):
        wraps_tuple = tuple(w for w in wraps_tuple if w != WrapKind.FLEXIBLE_LOOSE)
    if (
        parent_type == NodeType.ROW
        and child.type == NodeType.TEXT
        and WrapKind.FLEXIBLE_LOOSE in wraps_tuple
    ):
        from figma_flutter_agent.generator.layout.flex_policy import (
            row_is_tight_horizontal_pill_label,
        )

        if row_is_tight_horizontal_pill_label(parent):
            wraps_tuple = tuple(
                WrapKind.EXPANDED if wrap == WrapKind.FLEXIBLE_LOOSE else wrap
                for wrap in wraps_tuple
            )
    return wraps_tuple, input_metrics


def min_input_height(frame_height: float | None) -> float:
    """Universal touch minimum for INPUT emit."""
    base = frame_height if frame_height is not None and frame_height > 0 else _MIN_TOUCH_HEIGHT
    return max(base, _MIN_TOUCH_HEIGHT)
