"""Eligibility filters for widget extraction candidates."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_MIN_SUBTREE_AREA = 12_000.0


def is_trivial_extraction_candidate(node: CleanDesignTreeNode) -> bool:
    """Return True when a node is too small or inline-only to extract as a widget."""
    from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

    if must_inline_extracted_widget_host(node):
        return True
    if not node.children:
        return node.type in {NodeType.TEXT, NodeType.VECTOR, NodeType.IMAGE}
    if _is_single_text_leaf(node):
        return True
    return _subtree_area(node) < _MIN_SUBTREE_AREA and len(node.children) <= 1


def is_eligible_extraction_candidate(node: CleanDesignTreeNode) -> bool:
    """Return True when a node may be extracted as a standalone widget."""
    if is_trivial_extraction_candidate(node):
        return False
    return bool(node.children) or node.component_ref is not None


def _is_single_text_leaf(node: CleanDesignTreeNode) -> bool:
    if len(node.children) != 1:
        return False
    child = node.children[0]
    return child.type == NodeType.TEXT and not child.children


def _subtree_area(node: CleanDesignTreeNode) -> float:
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    if width > 0 and height > 0:
        return float(width) * float(height)
    return _MIN_SUBTREE_AREA
