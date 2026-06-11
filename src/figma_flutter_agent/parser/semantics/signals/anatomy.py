"""Tier-2 anatomy signals (structure only, no name/label matching)."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.models import TierSignals
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _child_type_counts(node: CleanDesignTreeNode) -> dict[NodeType, int]:
    counts: dict[NodeType, int] = {}
    for child in node.children:
        counts[child.type] = counts.get(child.type, 0) + 1
    return counts


def collect_anatomy_signals(node: CleanDesignTreeNode) -> TierSignals:
    """Collect tier-2 structural anatomy signals."""
    hits: dict[str, object] = {}
    score = 0.0
    counts = _child_type_counts(node)
    hits["child_type_counts"] = {key.value: value for key, value in counts.items()}
    hits["child_count"] = len(node.children)

    if node.type == NodeType.BUTTON:
        score = max(score, 0.8)
        hits["interactive_surface"] = "button"
    elif node.type == NodeType.INPUT:
        score = max(score, 0.85)
        hits["interactive_surface"] = "input"
    elif node.type in {NodeType.CHECKBOX, NodeType.SWITCH, NodeType.RADIO, NodeType.RADIO_GROUP}:
        score = max(score, 0.9)
        hits["interactive_surface"] = node.type.value
    elif node.type == NodeType.DROPDOWN:
        score = max(score, 0.88)
        hits["interactive_surface"] = "dropdown"
    elif node.type == NodeType.SLIDER:
        score = max(score, 0.88)
        hits["interactive_surface"] = "slider"
    elif node.type == NodeType.CARD:
        score = max(score, 0.75)
        hits["container_surface"] = "card"
    elif node.type == NodeType.BOTTOM_NAV:
        score = max(score, 0.9)
        hits["nav_surface"] = "bottom_nav"
    elif node.type == NodeType.TABS:
        score = max(score, 0.88)
        hits["nav_surface"] = "tabs"
    elif node.type == NodeType.CAROUSEL:
        score = max(score, 0.85)
        hits["container_surface"] = "carousel"
    elif node.type == NodeType.GRID:
        score = max(score, 0.85)
        hits["container_surface"] = "grid"
    elif node.type in {NodeType.ROW, NodeType.STACK, NodeType.WRAP} and len(node.children) >= 3:
        from figma_flutter_agent.parser.interaction import (
            hosts_compact_checkbox_control,
            looks_like_weekday_chip_stack,
        )

        if looks_like_weekday_chip_stack(node):
            score = max(score, 0.82)
            hits["chip_row"] = True
        if hosts_compact_checkbox_control(node):
            score = max(score, 0.8)
            hits["checkbox_row"] = True

    if node.type == NodeType.STACK and len(node.children) == 2:
        types = {child.type for child in node.children}
        if (NodeType.IMAGE in types or NodeType.VECTOR in types) and NodeType.TEXT in types:
            score = max(score, 0.7)
            hits["list_tile_shape"] = True

    return TierSignals(anatomy_score=min(score, 1.0), anatomy_hits=hits)
