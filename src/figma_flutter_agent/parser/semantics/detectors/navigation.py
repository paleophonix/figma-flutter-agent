"""Navigation semantic detectors."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.detectors._base import (
    RuleDetector,
    _child_types,
    _count_type,
    _extent,
    _variant_axis_value,
)
from figma_flutter_agent.parser.semantics.models import DetectorContext, SignalTier
from figma_flutter_agent.schemas import NodeType, WidgetIrKind


def _is_nav_bottom_bar(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if node.type != NodeType.BOTTOM_NAV:
        return False
    from figma_flutter_agent.parser.interaction.product import (
        layout_fact_bottom_nav_is_checkout_footer,
    )

    return not layout_fact_bottom_nav_is_checkout_footer(node)


def _is_nav_tab_bar(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if node.type == NodeType.TABS:
        return True
    axis = _variant_axis_value(node, "type", "role")
    return axis is not None and "tab" in axis and node.type in {NodeType.ROW, NodeType.STACK}


def _is_nav_scroll_host(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if node.scroll_axis != "vertical":
        return False
    if ctx.ir_node.layout_hints is not None and ctx.ir_node.layout_hints.scroll_axis == "vertical":
        return True
    return node.type in {NodeType.COLUMN, NodeType.STACK}


def _is_nav_app_bar(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    if node.type not in {NodeType.ROW, NodeType.STACK}:
        return False
    width, height = _extent(node)
    if height is not None and height > 96:
        return False
    types = _child_types(node)
    return NodeType.TEXT in types and (NodeType.BUTTON in types or NodeType.VECTOR in types)


def _is_nav_drawer(ctx: DetectorContext) -> bool:
    axis = _variant_axis_value(ctx.clean_node, "type", "role")
    return axis is not None and "drawer" in axis


def _is_nav_stepper(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    axis = _variant_axis_value(node, "type", "role")
    if axis and "step" in axis and "input" not in axis:
        return True
    return node.type == NodeType.ROW and _count_type(node, NodeType.CONTAINER) >= 3


def _is_nav_pagination(ctx: DetectorContext) -> bool:
    node = ctx.clean_node
    axis = _variant_axis_value(node, "type", "role")
    if axis and ("pagination" in axis or "pager" in axis):
        return True
    if node.type != NodeType.ROW:
        return False
    compact_children = sum(
        1
        for child in node.children
        if child.type in {NodeType.CONTAINER, NodeType.VECTOR}
        and child.sizing.width is not None
        and child.sizing.width <= 24
    )
    return compact_children >= 3


NAVIGATION_DETECTORS: tuple[RuleDetector, ...] = (
    RuleDetector(
        WidgetIrKind.NAV_BOTTOM_BAR,
        predicate=_is_nav_bottom_bar,
        tier=SignalTier.ANATOMY,
        base_confidence=0.92,
        evidence_key="nav_bottom_bar",
    ),
    RuleDetector(
        WidgetIrKind.NAV_TAB_BAR,
        predicate=_is_nav_tab_bar,
        tier=SignalTier.ANATOMY,
        base_confidence=0.88,
        evidence_key="nav_tab_bar",
    ),
    RuleDetector(
        WidgetIrKind.NAV_SCROLL_HOST,
        predicate=_is_nav_scroll_host,
        tier=SignalTier.ANATOMY,
        base_confidence=0.86,
        evidence_key="nav_scroll_host",
    ),
    RuleDetector(
        WidgetIrKind.NAV_APP_BAR,
        predicate=_is_nav_app_bar,
        tier=SignalTier.GEOMETRY,
        base_confidence=0.8,
        evidence_key="nav_app_bar",
    ),
    RuleDetector(
        WidgetIrKind.NAV_DRAWER,
        predicate=_is_nav_drawer,
        tier=SignalTier.PROPERTIES,
        base_confidence=0.88,
        evidence_key="nav_drawer",
    ),
    RuleDetector(
        WidgetIrKind.NAV_STEPPER,
        predicate=_is_nav_stepper,
        tier=SignalTier.ANATOMY,
        base_confidence=0.82,
        evidence_key="nav_stepper",
    ),
    RuleDetector(
        WidgetIrKind.NAV_PAGINATION,
        predicate=_is_nav_pagination,
        tier=SignalTier.ANATOMY,
        base_confidence=0.81,
        evidence_key="nav_pagination",
    ),
)
