"""Button and chip semantic detectors."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.detectors._base import (
    RuleDetector,
    _child_types,
    _count_type,
    _has_filled_surface,
    _has_outlined_surface,
    _is_compact_square,
    _signal_type,
    _variant_axis_value,
)
from figma_flutter_agent.parser.semantics.models import DetectorContext, SignalTier
from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
    count_compact_chip_stacks,
    count_tag_option_chips,
    is_static_segmented_number_row,
    is_tag_option_chip_group,
    layout_fact_compact_chip_stack,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrKind


def _is_button_node(ctx: DetectorContext) -> bool:
    return _signal_type(ctx.clean_node) == NodeType.BUTTON


def _is_button_filled(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    return _signal_type(node) == NodeType.BUTTON and _has_filled_surface(node)


def _is_button_outlined(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    return _signal_type(node) == NodeType.BUTTON and _has_outlined_surface(node)


def _is_button_text(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if _signal_type(node) != NodeType.BUTTON:
        return False
    if _has_filled_surface(node) or _has_outlined_surface(node):
        return False
    return NodeType.TEXT in _child_types(node)


def _is_button_fab(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    return _signal_type(node) == NodeType.BUTTON and _is_compact_square(node, max_side=56.0)


def _is_button_icon(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if _signal_type(node) != NodeType.BUTTON or not _is_compact_square(node, max_side=48.0):
        return False
    types = _child_types(node)
    return NodeType.VECTOR in types and NodeType.TEXT not in types


def _is_chip_row(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if is_tag_option_chip_group(node):
        return True
    if count_tag_option_chips(node) >= 2:
        return True
    if node.type == NodeType.STACK and layout_fact_compact_chip_stack(node):
        return True
    if node.type in {NodeType.ROW, NodeType.WRAP}:
        return count_compact_chip_stacks(node) >= 2
    return False


def _is_chip_choice(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if not _is_chip_row(ctx):
        return False
    if node.type in {NodeType.ROW, NodeType.WRAP} and _count_type(node, NodeType.BUTTON) >= 2:
        return False
    axis = _variant_axis_value(node, "type", "variant")
    return axis is None or "filter" not in axis


def _is_chip_filter(ctx: DetectorContext) -> bool:
    if not _is_chip_row(ctx):
        return False
    axis = _variant_axis_value(ctx.clean_node, "type", "variant")
    return axis is not None and "filter" in axis


def _is_chip_input(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if is_static_segmented_number_row(node):
        return False
    axis = _variant_axis_value(node, "type", "variant")
    if axis and "input" in axis:
        return True
    return (
        node.type in {NodeType.ROW, NodeType.WRAP, NodeType.STACK} and _count_input_like(node) >= 2
    )


def _count_input_like(node: CleanDesignTreeNode) -> int:
    return sum(
        1
        for child in node.children
        if _signal_type(child) in {NodeType.INPUT, NodeType.TEXT, NodeType.CONTAINER}
    )


def _is_chip_action(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    return _signal_type(node) == NodeType.BUTTON and NodeType.VECTOR in _child_types(node)


ACTION_DETECTORS: tuple[RuleDetector, ...] = (
    RuleDetector(
        WidgetIrKind.BUTTON_FILLED,
        predicate=_is_button_filled,
        tier=SignalTier.ANATOMY,
        base_confidence=0.86,
        evidence_key="button_filled",
    ),
    RuleDetector(
        WidgetIrKind.BUTTON_OUTLINED,
        predicate=_is_button_outlined,
        tier=SignalTier.ANATOMY,
        base_confidence=0.85,
        evidence_key="button_outlined",
    ),
    RuleDetector(
        WidgetIrKind.BUTTON_TEXT,
        predicate=_is_button_text,
        tier=SignalTier.ANATOMY,
        base_confidence=0.84,
        evidence_key="button_text",
    ),
    RuleDetector(
        WidgetIrKind.BUTTON_FAB,
        predicate=_is_button_fab,
        tier=SignalTier.GEOMETRY,
        base_confidence=0.82,
        evidence_key="button_fab",
    ),
    RuleDetector(
        WidgetIrKind.BUTTON_ICON,
        predicate=_is_button_icon,
        tier=SignalTier.ANATOMY,
        base_confidence=0.83,
        evidence_key="button_icon",
    ),
    RuleDetector(
        WidgetIrKind.CHIP_CHOICE,
        predicate=_is_chip_choice,
        tier=SignalTier.ANATOMY,
        base_confidence=0.85,
        evidence_key="chip_choice",
    ),
    RuleDetector(
        WidgetIrKind.CHIP_FILTER,
        predicate=_is_chip_filter,
        tier=SignalTier.PROPERTIES,
        base_confidence=0.84,
        evidence_key="chip_filter",
    ),
    RuleDetector(
        WidgetIrKind.CHIP_INPUT,
        predicate=_is_chip_input,
        tier=SignalTier.ANATOMY,
        base_confidence=0.82,
        evidence_key="chip_input",
    ),
    RuleDetector(
        WidgetIrKind.CHIP_ACTION,
        predicate=_is_chip_action,
        tier=SignalTier.ANATOMY,
        base_confidence=0.8,
        evidence_key="chip_action",
    ),
)
