"""Label helpers for navigation widgets."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.schemas import CleanDesignTreeNode


def first_descendant_text_label(
    node: CleanDesignTreeNode, *, max_depth: int = 8, depth: int = 0
) -> str | None:
    if depth > max_depth:
        return None
    if node.text and node.text.strip():
        return node.text.strip()
    for child in node.children:
        found = first_descendant_text_label(
            child,
            max_depth=max_depth,
            depth=depth + 1,
        )
        if found:
            return found
    return None


def label_from_child(child: CleanDesignTreeNode) -> str:
    """Resolve a tab or nav item label from a child node."""
    label = first_descendant_text_label(child)
    if label:
        return escape_dart_string(label)
    return escape_dart_string(child.name)


def tab_label_from_child(child: CleanDesignTreeNode) -> str:
    """Use panel frame names for tab labels (not inner headline text)."""
    return escape_dart_string(child.name)
