"""Structural compact-chip and Figma Tag option-chip signals (no label lexicon)."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_CHIP_MIN_SIZE = 32.0
_CHIP_MAX_SIZE = 56.0
_TAG_OPTION_GROUP_TYPES = frozenset({NodeType.STACK, NodeType.ROW, NodeType.WRAP})


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


def is_tag_option_chip_row(node: CleanDesignTreeNode) -> bool:
    """Return True for Figma ``Tag`` component rows used as choice options."""
    from figma_flutter_agent.parser.interaction.chip_variant import is_tag_component_chip_row

    return is_tag_component_chip_row(node)


def count_tag_option_chips(node: CleanDesignTreeNode) -> int:
    """Count direct children that are Figma ``Tag`` option chips."""
    return sum(1 for child in node.children if is_tag_option_chip_row(child))


def is_tag_option_chip_group(node: CleanDesignTreeNode) -> bool:
    """Return True when a container hosts two or more ``Tag`` option chips."""
    if node.type not in _TAG_OPTION_GROUP_TYPES or len(node.children) < 2:
        return False
    tag_count = count_tag_option_chips(node)
    if tag_count >= 2:
        return True
    if node.name.strip().lower() == "chips" and tag_count >= 1 and len(node.children) >= 2:
        return all(is_tag_option_chip_row(child) for child in node.children)
    return False


def stack_should_preserve_absolute_tag_chips(stack: CleanDesignTreeNode) -> bool:
    """True when tag option chips keep absolute ``Stack`` placement."""
    if not is_tag_option_chip_group(stack):
        return False
    return all(child.stack_placement is not None for child in stack.children)


def stack_should_flow_as_tag_option_wrap(stack: CleanDesignTreeNode) -> bool:
    """True when tag chips should flow in a ``Wrap`` instead of a ``Column``."""
    if not is_tag_option_chip_group(stack):
        return False
    return not stack_should_preserve_absolute_tag_chips(stack)


def is_static_segmented_number_row(node: CleanDesignTreeNode) -> bool:
    """Return True for masked card numbers rendered as absolute text segments."""
    if node.type not in _TAG_OPTION_GROUP_TYPES | {NodeType.STACK, NodeType.WRAP}:
        return False
    text_children = [child for child in node.children if child.type == NodeType.TEXT]
    if len(text_children) < 2:
        return False
    if any(child.type == NodeType.INPUT for child in node.children):
        return False
    height = node.sizing.height
    if height is None and node.stack_placement is not None:
        height = node.stack_placement.height
    if height is not None and float(height) > 36.0:
        return False
    return all(child.stack_placement is not None for child in text_children)


__all__ = [
    "count_compact_chip_stacks",
    "count_tag_option_chips",
    "is_compact_chip_stack",
    "is_tag_option_chip_group",
    "is_tag_option_chip_row",
    "is_static_segmented_number_row",
    "stack_should_flow_as_tag_option_wrap",
    "stack_should_preserve_absolute_tag_chips",
]
