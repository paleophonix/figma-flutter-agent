"""Overlay and feedback semantic detectors."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.detectors._base import (
    RuleDetector,
    _extent,
    _variant_axis_value,
)
from figma_flutter_agent.parser.semantics.models import DetectorContext, SignalTier
from figma_flutter_agent.schemas import NodeType, WidgetIrKind


def _overlay_signal(ctx: DetectorContext) -> bool:
    return ctx.signals.overlay_signal or ctx.clean_node.type == NodeType.DIALOG


def _is_overlay_dialog(ctx: DetectorContext) -> bool:
    return _overlay_signal(ctx) and ctx.clean_node.type == NodeType.DIALOG


def _is_overlay_bottom_sheet(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role")
    if axis and "sheet" in axis:
        return _overlay_signal(ctx)
    node = ctx.clean_node
    width, height = _extent(node)
    if width is None or height is None:
        return False
    return _overlay_signal(ctx) and node.type in {NodeType.STACK, NodeType.COLUMN} and height <= width


def _is_overlay_snackbar(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role")
    if axis and ("snackbar" in axis or "toast" in axis):
        return True
    node = ctx.clean_node
    width, height = _extent(node)
    if width is None or height is None:
        return False
    return node.type in {NodeType.ROW, NodeType.STACK} and height <= 72.0 and width >= 160.0


def _is_overlay_banner(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role")
    if axis and "banner" in axis:
        return True
    node = ctx.clean_node
    width, height = _extent(node)
    if width is None or height is None:
        return False
    return node.type in {NodeType.ROW, NodeType.STACK} and height <= 96.0 and width >= 200.0


def _is_feedback_loader(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role", "state")
    if axis and ("loader" in axis or "loading" in axis or "spinner" in axis):
        return True
    node = ctx.clean_node
    return node.type == NodeType.VECTOR and _is_compact_loader(node)


def _is_compact_loader(node) -> bool:
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    return max(width, height) <= 48.0


def _is_feedback_skeleton(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role")
    if axis and "skeleton" in axis:
        return True
    node = ctx.clean_node
    if node.type != NodeType.COLUMN:
        return False
    placeholders = sum(
        1
        for child in node.children
        if child.type == NodeType.CONTAINER and child.style.background_color
    )
    return placeholders >= 2


def _is_feedback_tooltip(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role")
    if axis and "tooltip" in axis:
        return True
    node = ctx.clean_node
    width, height = _extent(node)
    if width is None or height is None:
        return False
    return node.type == NodeType.STACK and max(width, height) <= 120.0


OVERLAY_DETECTORS: tuple[RuleDetector, ...] = (
    RuleDetector(
        WidgetIrKind.OVERLAY_DIALOG,
        predicate=_is_overlay_dialog,
        tier=SignalTier.PROPERTIES,
        base_confidence=0.92,
        evidence_key="overlay_dialog",
    ),
    RuleDetector(
        WidgetIrKind.OVERLAY_BOTTOM_SHEET,
        predicate=_is_overlay_bottom_sheet,
        tier=SignalTier.PROPERTIES,
        base_confidence=0.88,
        evidence_key="overlay_bottom_sheet",
    ),
    RuleDetector(
        WidgetIrKind.OVERLAY_SNACKBAR,
        predicate=_is_overlay_snackbar,
        tier=SignalTier.ANATOMY,
        base_confidence=0.82,
        evidence_key="overlay_snackbar",
    ),
    RuleDetector(
        WidgetIrKind.OVERLAY_BANNER,
        predicate=_is_overlay_banner,
        tier=SignalTier.ANATOMY,
        base_confidence=0.82,
        evidence_key="overlay_banner",
    ),
    RuleDetector(
        WidgetIrKind.FEEDBACK_LOADER,
        predicate=_is_feedback_loader,
        tier=SignalTier.PROPERTIES,
        base_confidence=0.84,
        evidence_key="feedback_loader",
    ),
    RuleDetector(
        WidgetIrKind.FEEDBACK_SKELETON,
        predicate=_is_feedback_skeleton,
        tier=SignalTier.ANATOMY,
        base_confidence=0.83,
        evidence_key="feedback_skeleton",
    ),
    RuleDetector(
        WidgetIrKind.FEEDBACK_TOOLTIP,
        predicate=_is_feedback_tooltip,
        tier=SignalTier.PROPERTIES,
        base_confidence=0.8,
        evidence_key="feedback_tooltip",
    ),
)
