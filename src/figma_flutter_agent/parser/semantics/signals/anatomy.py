"""Tier-2 anatomy signals (structure only, no name/label matching)."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.models import TierSignals
from figma_flutter_agent.parser.semantics.signals.type_trust import semantic_signal_type
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _child_type_counts(node: CleanDesignTreeNode) -> dict[NodeType, int]:
    counts: dict[NodeType, int] = {}
    for child in node.children:
        effective = semantic_signal_type(child)
        counts[effective] = counts.get(effective, 0) + 1
    return counts


def collect_anatomy_signals(node: CleanDesignTreeNode) -> TierSignals:
    """Collect tier-2 structural anatomy signals."""
    hits: dict[str, object] = {}
    score = 0.0
    signal_type = semantic_signal_type(node)
    counts = _child_type_counts(node)
    hits["child_type_counts"] = {key.value: value for key, value in counts.items()}
    hits["child_count"] = len(node.children)

    if signal_type == NodeType.BUTTON:
        score = max(score, 0.8)
        hits["interactive_surface"] = "button"
    elif signal_type == NodeType.INPUT:
        score = max(score, 0.85)
        hits["interactive_surface"] = "input"
    elif signal_type in {NodeType.CHECKBOX, NodeType.SWITCH, NodeType.RADIO, NodeType.RADIO_GROUP}:
        score = max(score, 0.9)
        hits["interactive_surface"] = signal_type.value
    elif signal_type == NodeType.DROPDOWN:
        score = max(score, 0.88)
        hits["interactive_surface"] = "dropdown"
    elif signal_type == NodeType.SLIDER:
        score = max(score, 0.88)
        hits["interactive_surface"] = "slider"
    elif signal_type == NodeType.CARD:
        score = max(score, 0.75)
        hits["container_surface"] = "card"
    elif signal_type == NodeType.BOTTOM_NAV:
        score = max(score, 0.9)
        hits["nav_surface"] = "bottom_nav"
    elif signal_type == NodeType.TABS:
        score = max(score, 0.88)
        hits["nav_surface"] = "tabs"
    elif signal_type == NodeType.CAROUSEL:
        score = max(score, 0.85)
        hits["container_surface"] = "carousel"
    elif signal_type == NodeType.GRID:
        score = max(score, 0.85)
        hits["container_surface"] = "grid"
    elif signal_type in {NodeType.ROW, NodeType.STACK, NodeType.WRAP} and len(node.children) >= 2:
        from figma_flutter_agent.parser.interaction import (
            layout_fact_hosts_compact_checkbox_control,
        )
        from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
            count_compact_chip_stacks,
            count_tag_option_chips,
            is_tag_option_chip_group,
            layout_fact_compact_chip_stack,
        )

        if is_tag_option_chip_group(node) or count_tag_option_chips(node) >= 2:
            score = max(score, 0.84)
            hits["tag_option_chip_row"] = True
            hits["chip_row"] = True
        elif layout_fact_compact_chip_stack(node) or count_compact_chip_stacks(node) >= 2:
            score = max(score, 0.82)
            hits["chip_row"] = True
        if layout_fact_hosts_compact_checkbox_control(node):
            score = max(score, 0.8)
            hits["checkbox_row"] = True
            hits["signalSource"] = "legacy_interaction"

    if signal_type == NodeType.STACK and len(node.children) == 2:
        types = {semantic_signal_type(child) for child in node.children}
        if (NodeType.IMAGE in types or NodeType.VECTOR in types) and NodeType.TEXT in types:
            score = max(score, 0.7)
            hits["list_tile_shape"] = True

    return TierSignals(anatomy_score=min(score, 1.0), anatomy_hits=hits)
