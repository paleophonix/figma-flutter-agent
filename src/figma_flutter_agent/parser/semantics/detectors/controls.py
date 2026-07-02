"""Form control semantic detectors."""

from __future__ import annotations

from figma_flutter_agent.parser.interaction import layout_fact_hosts_compact_checkbox_control
from figma_flutter_agent.parser.semantics.detectors._base import RuleDetector, _variant_axis_value
from figma_flutter_agent.parser.semantics.models import DetectorContext, SignalTier
from figma_flutter_agent.schemas import NodeType, WidgetIrKind


def _is_checkbox(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    return node.type == NodeType.CHECKBOX or layout_fact_hosts_compact_checkbox_control(node)


def _is_switch(ctx: DetectorContext) -> bool:
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_switch_hosts_segmented_options,
    )

    if layout_fact_switch_hosts_segmented_options(ctx.clean_node):
        return False
    return ctx.clean_node.type == NodeType.SWITCH


def _is_radio(ctx: DetectorContext) -> bool:
    return ctx.clean_node.type in {NodeType.RADIO, NodeType.RADIO_GROUP}


def _is_segmented(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_switch_hosts_segmented_options,
    )

    if layout_fact_switch_hosts_segmented_options(node):
        return True
    axis = _variant_axis_value(node, "type", "control", "variant")
    if axis and "segment" in axis:
        return True
    if node.type not in {NodeType.ROW, NodeType.TABS}:
        return False
    if len(node.children) < 2:
        return False
    return all(
        child.type in {NodeType.BUTTON, NodeType.CONTAINER, NodeType.TEXT}
        for child in node.children
    )


CONTROL_DETECTORS: tuple[RuleDetector, ...] = (
    RuleDetector(
        WidgetIrKind.CONTROL_CHECKBOX,
        predicate=_is_checkbox,
        tier=SignalTier.ANATOMY,
        base_confidence=0.9,
        evidence_key="control_checkbox",
    ),
    RuleDetector(
        WidgetIrKind.CONTROL_SWITCH,
        predicate=_is_switch,
        tier=SignalTier.ANATOMY,
        base_confidence=0.9,
        evidence_key="control_switch",
    ),
    RuleDetector(
        WidgetIrKind.CONTROL_RADIO,
        predicate=_is_radio,
        tier=SignalTier.ANATOMY,
        base_confidence=0.9,
        evidence_key="control_radio",
    ),
    RuleDetector(
        WidgetIrKind.CONTROL_SEGMENTED,
        predicate=_is_segmented,
        tier=SignalTier.ANATOMY,
        base_confidence=0.84,
        evidence_key="control_segmented",
    ),
)
