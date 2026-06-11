"""Input and data-entry semantic detectors."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.detectors._base import (
    RuleDetector,
    _child_types,
    _count_type,
    _variant_axis_value,
)
from figma_flutter_agent.parser.semantics.models import DetectorContext, SignalTier
from figma_flutter_agent.schemas import NodeType, WidgetIrKind


def _is_input_text_field(ctx: DetectorContext) -> bool:
    return ctx.clean_node.type == NodeType.INPUT


def _is_input_search_bar(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if node.type not in {NodeType.INPUT, NodeType.ROW, NodeType.STACK}:
        return False
    axis = _variant_axis_value(node, "type", "role")
    if axis and "search" in axis:
        return True
    types = _child_types(node)
    return NodeType.VECTOR in types and NodeType.TEXT in types and len(node.children) <= 4


def _is_input_dropdown(ctx: DetectorContext) -> bool:
    return ctx.clean_node.type == NodeType.DROPDOWN


def _is_input_picker_date(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role", "variant")
    return axis is not None and "date" in axis


def _is_input_picker_time(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role", "variant")
    return axis is not None and "time" in axis


def _is_input_stepper(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if node.type not in {NodeType.ROW, NodeType.STACK}:
        return False
    if _count_type(node, NodeType.BUTTON) >= 2 and _count_type(node, NodeType.TEXT) >= 1:
        return True
    axis = _variant_axis_value(node, "type", "control")
    return axis is not None and "stepper" in axis


def _is_input_slider(ctx: DetectorContext) -> bool:
    return ctx.clean_node.type == NodeType.SLIDER


def _is_input_file_uploader(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    axis = _variant_axis_value(node, "type", "role")
    if axis and ("upload" in axis or "file" in axis):
        return True
    types = _child_types(node)
    return NodeType.BUTTON in types and (NodeType.VECTOR in types or NodeType.IMAGE in types)


INPUT_DETECTORS: tuple[RuleDetector, ...] = (
    RuleDetector(
        WidgetIrKind.INPUT_TEXT_FIELD,
        predicate=_is_input_text_field,
        tier=SignalTier.ANATOMY,
        base_confidence=0.88,
        evidence_key="input_text_field",
    ),
    RuleDetector(
        WidgetIrKind.INPUT_SEARCH_BAR,
        predicate=_is_input_search_bar,
        tier=SignalTier.ANATOMY,
        base_confidence=0.82,
        evidence_key="input_search_bar",
    ),
    RuleDetector(
        WidgetIrKind.INPUT_DROPDOWN,
        predicate=_is_input_dropdown,
        tier=SignalTier.ANATOMY,
        base_confidence=0.9,
        evidence_key="input_dropdown",
    ),
    RuleDetector(
        WidgetIrKind.INPUT_PICKER_DATE,
        predicate=_is_input_picker_date,
        tier=SignalTier.PROPERTIES,
        base_confidence=0.86,
        evidence_key="input_picker_date",
    ),
    RuleDetector(
        WidgetIrKind.INPUT_PICKER_TIME,
        predicate=_is_input_picker_time,
        tier=SignalTier.PROPERTIES,
        base_confidence=0.86,
        evidence_key="input_picker_time",
    ),
    RuleDetector(
        WidgetIrKind.INPUT_STEPPER,
        predicate=_is_input_stepper,
        tier=SignalTier.ANATOMY,
        base_confidence=0.84,
        evidence_key="input_stepper",
    ),
    RuleDetector(
        WidgetIrKind.INPUT_SLIDER,
        predicate=_is_input_slider,
        tier=SignalTier.ANATOMY,
        base_confidence=0.9,
        evidence_key="input_slider",
    ),
    RuleDetector(
        WidgetIrKind.INPUT_FILE_UPLOADER,
        predicate=_is_input_file_uploader,
        tier=SignalTier.ANATOMY,
        base_confidence=0.83,
        evidence_key="input_file_uploader",
    ),
)
