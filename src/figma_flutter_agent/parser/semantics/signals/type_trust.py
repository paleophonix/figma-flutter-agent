"""Trust policy for clean-tree ``node.type`` in semantic signals and detectors."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.type_truth import (
    is_legacy_semantic_type_node,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

LAUNDERED_LEGACY_TYPES = frozenset(
    {
        NodeType.INPUT,
        NodeType.BUTTON,
        NodeType.CARD,
    }
)


def semantic_signal_type(node: CleanDesignTreeNode) -> NodeType:
    """Return a type safe for semantic scoring when legacy name-hints laundered the parse.

    Legacy ``infer_leaf_type`` assignments (layer names like ``input`` / ``button`` /
    ``card``) downgrade to ``CONTAINER`` so anatomy and detectors cannot treat the
    laundered passport as authoritative evidence.

    Args:
        node: Clean-tree node under classification.

    Returns:
        ``node.type`` or ``NodeType.CONTAINER`` when the id is legacy-laundered.
    """
    if is_legacy_semantic_type_node(node.id) and node.type in LAUNDERED_LEGACY_TYPES:
        return NodeType.CONTAINER
    return node.type


def legacy_blocks_semantic_candidates(node: CleanDesignTreeNode) -> bool:
    """Return True when no semantic MVP kinds should be considered for ``node``."""
    return is_legacy_semantic_type_node(node.id) and node.type in LAUNDERED_LEGACY_TYPES
