"""Artboard width helpers shared by normalize and layout emit."""

from __future__ import annotations

from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, SizingMode

_MOBILE_ARTBOARD_MAX_WIDTH = 480.0


def resolve_artboard_width(root: CleanDesignTreeNode) -> float | None:
    """Return the root frame width when it represents a bounded artboard."""
    width = root.sizing.width
    if width is None or width <= 0:
        return None
    if root.sizing.width_mode not in {SizingMode.FIXED, SizingMode.FILL}:
        return None
    return float(width)


def is_mobile_artboard_width(width: float | None) -> bool:
    """Return True when the artboard matches a phone-sized Figma frame."""
    return width is not None and width <= _MOBILE_ARTBOARD_MAX_WIDTH


def clamp_oversized_frame_widths_to_artboard(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Clamp descendant frame widths that exceed the root artboard span.

    Figma export rounding can yield a 391px column inside a 390px frame; emitting
    that width in a 390px viewport shifts content horizontally in Chrome preview.

    Args:
        root: Parsed clean design tree root (typically a ``STACK`` artboard).

    Returns:
        Tree copy with oversized ``sizing.width`` values capped to the artboard.
    """
    artboard_width = resolve_artboard_width(root)
    if artboard_width is None:
        return root

    def _walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [_walk(child) for child in node.children]
        width = node.sizing.width
        if width is not None and width > artboard_width:
            sizing = node.sizing.model_copy(update={"width": artboard_width})
            return node.model_copy(update={"sizing": sizing, "children": children})
        return node.model_copy(update={"children": children})

    return _walk(deep_copy_clean_tree(root))
