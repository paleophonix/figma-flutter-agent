"""Button host layout-flow helpers (geometry-only, no marketing copy)."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def button_vertical_auto_layout_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when spaced button children exactly fill the host height in order.

    Args:
        node: Parsed clean-tree button host.

    Returns:
        True when vertical auto-layout spacing matches child panel heights.
    """
    from figma_flutter_agent.generator.geometry.affine import geom_epsilon

    spacing = float(node.spacing or 0.0)
    if spacing <= 0.0:
        return False
    panel_types = {
        NodeType.ROW,
        NodeType.COLUMN,
        NodeType.STACK,
        NodeType.CONTAINER,
        NodeType.CARD,
    }
    panels = [child for child in node.children if child.type in panel_types]
    if len(panels) < 2:
        return False
    heights: list[float] = []
    for panel in panels:
        height = panel.sizing.height
        if height is None or height <= 0:
            return False
        heights.append(float(height))
    parent_height = node.sizing.height
    if parent_height is None or parent_height <= 0:
        return False
    stack_height = sum(heights) + spacing * (len(heights) - 1)
    return abs(stack_height - float(parent_height)) <= geom_epsilon() + 0.5


__all__ = ["button_vertical_auto_layout_stack"]
