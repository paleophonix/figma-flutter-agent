"""Artboard width helpers shared by normalize and layout emit."""

from __future__ import annotations

from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, SizingMode

_MOBILE_ARTBOARD_MAX_WIDTH = 480.0
_ARTBOARD_BOUNDED_WIDTH_RATIO = 0.9
_ARTBOARD_WIDTH_TOLERANCE = 1.5
# Phone frames taller than ~15:9 need vertical scroll in browser viewports (golden keeps full artboard).
_TALL_MOBILE_ARTBOARD_ASPECT = 2.25


def resolve_artboard_width(root: CleanDesignTreeNode) -> float | None:
    """Return the root frame width when it represents a bounded artboard."""
    width = root.sizing.width
    if width is None or width <= 0:
        return None
    if root.sizing.width_mode not in {SizingMode.FIXED, SizingMode.FILL}:
        return None
    return float(width)


def resolve_artboard_height(root: CleanDesignTreeNode) -> float | None:
    """Return the root frame height when it represents a bounded artboard."""
    if root.geometry_frame is not None and root.geometry_frame.world_aabb.height > 0:
        return float(root.geometry_frame.world_aabb.height)
    height = root.sizing.height
    if height is None or height <= 0:
        return None
    if root.sizing.height_mode not in {SizingMode.FIXED, SizingMode.FILL, SizingMode.HUG}:
        return None
    return float(height)


def is_mobile_artboard_width(width: float | None) -> bool:
    """Return True when the artboard matches a phone-sized Figma frame."""
    return width is not None and width <= _MOBILE_ARTBOARD_MAX_WIDTH


def is_tall_mobile_artboard(
    width: float | None,
    height: float | None,
) -> bool:
    """Return True when a phone artboard is taller than a typical device viewport."""
    if not is_mobile_artboard_width(width):
        return False
    if width is None or height is None or width <= 0 or height <= 0:
        return False
    return float(height) > float(width) * _TALL_MOBILE_ARTBOARD_ASPECT


def is_artboard_bounded_layout_width(
    node_width: float | None,
    design_artboard_width: float | None,
) -> bool:
    """Return True when a frame width matches the phone artboard content span.

    Figma phone frames often emit 390px roots with ~357px header bands; both should
    stretch when the layout is hosted in a wide viewport (spec §7.3 / §9).
    """
    if node_width is None or design_artboard_width is None:
        return False
    if node_width <= 0 or design_artboard_width <= 0:
        return False
    if abs(float(node_width) - float(design_artboard_width)) <= _ARTBOARD_WIDTH_TOLERANCE:
        return True
    return float(node_width) >= float(design_artboard_width) * _ARTBOARD_BOUNDED_WIDTH_RATIO


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
