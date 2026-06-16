"""Visible-paint helpers for extracted widget materialization."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrNode


def subtree_has_visible_paint(node: CleanDesignTreeNode, *, max_depth: int = 6) -> bool:
    """Return True when a subtree still carries drawable text, imagery, or controls."""
    if max_depth < 0:
        return False
    if node.type == NodeType.TEXT and (node.text or "").strip():
        return True
    if node.image_asset_key or node.vector_asset_key:
        return True
    if node.type in {NodeType.IMAGE, NodeType.VECTOR, NodeType.BUTTON}:
        return True
    return any(subtree_has_visible_paint(child, max_depth=max_depth - 1) for child in node.children)


def should_render_extracted_widget_from_clean_tree(
    widget_ir: WidgetIrNode,
    subtree: CleanDesignTreeNode,
) -> bool:
    """Prefer deterministic clean-tree emit when LLM IR omitted children but paint remains."""
    if widget_ir.children:
        return False
    if len(subtree.children) >= 2:
        return True
    return subtree_has_visible_paint(subtree)
