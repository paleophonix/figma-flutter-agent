"""Structural compact-chip signals (no label lexicon)."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_CHIP_MIN_SIZE = 32.0
_CHIP_MAX_SIZE = 56.0


def is_compact_chip_stack(node: CleanDesignTreeNode) -> bool:
    """Return True for a fixed square stack with exactly one text child.

    Args:
        node: Clean-tree node under test.

    Returns:
        True when the node matches compact chip anatomy.
    """
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (_CHIP_MIN_SIZE <= float(width) <= _CHIP_MAX_SIZE):
        return False
    if not (_CHIP_MIN_SIZE <= float(height) <= _CHIP_MAX_SIZE):
        return False
    text_children = [child for child in node.children if child.type == NodeType.TEXT]
    return len(text_children) == 1


def count_compact_chip_stacks(node: CleanDesignTreeNode) -> int:
    """Count direct children that match compact chip anatomy."""
    return sum(1 for child in node.children if is_compact_chip_stack(child))


__all__ = ["count_compact_chip_stacks", "is_compact_chip_stack"]
