"""Clean node to IR kind mapping."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrKind


def ir_kind_for_clean_node(clean: CleanDesignTreeNode) -> WidgetIrKind:
    if clean.type == NodeType.STACK:
        return WidgetIrKind.STACK
    if clean.type == NodeType.COLUMN:
        return WidgetIrKind.COLUMN
    if clean.type == NodeType.ROW:
        return WidgetIrKind.ROW
    if clean.type == NodeType.WRAP:
        return WidgetIrKind.WRAP
    if clean.type == NodeType.TEXT:
        return WidgetIrKind.TEXT
    if clean.type == NodeType.BUTTON:
        return WidgetIrKind.BUTTON
    if clean.type == NodeType.INPUT:
        return WidgetIrKind.INPUT
    if clean.type == NodeType.CONTAINER:
        return WidgetIrKind.CONTAINER
    if clean.type == NodeType.IMAGE:
        return WidgetIrKind.IMAGE
    return WidgetIrKind.AUTO
