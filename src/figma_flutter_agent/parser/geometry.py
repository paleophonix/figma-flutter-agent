"""Geometry-only classification for clean design tree nodes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_SOCIAL_ROW_MIN_HEIGHT = 44.0
_SOCIAL_ROW_MAX_HEIGHT = 72.0
_SOCIAL_ROW_MIN_WIDTH = 200.0
_SOCIAL_ICON_BUTTON_MIN_WIDTH = 40.0
_SOCIAL_ICON_BUTTON_MAX_WIDTH = 96.0
_SOCIAL_ICON_BUTTON_MIN_HEIGHT = 40.0
_SOCIAL_ICON_BUTTON_MAX_HEIGHT = 56.0
_ICON_MAX_SIZE = 36.0
_LABEL_MIN_WIDTH = 80.0


def _placement_box(
    node: CleanDesignTreeNode,
) -> tuple[float, float, float, float] | None:
    placement = node.stack_placement
    if placement is None:
        return None
    width = placement.width
    height = placement.height
    if width is None or height is None:
        if placement.right and placement.left:
            width = placement.right - placement.left
        if placement.bottom and placement.top:
            height = placement.bottom - placement.top
    if width is None or height is None:
        return None
    return placement.left, placement.top, width, height


def _child_extent(
    node: CleanDesignTreeNode,
) -> tuple[float | None, float | None]:
    """Return width/height from stack placement or node sizing."""
    box = _placement_box(node)
    if box is not None:
        return box[2], box[3]
    return node.sizing.width, node.sizing.height


def _compact_icon_stack(child: CleanDesignTreeNode) -> bool:
    """True for a small stack whose children are mostly vectors (provider icon)."""
    if child.type != NodeType.STACK:
        return False
    width, height = _child_extent(child)
    if width is None or height is None:
        return False
    if width > _ICON_MAX_SIZE * 2 or height > _ICON_MAX_SIZE * 2:
        return False
    vectors = sum(1 for item in child.children if item.type == NodeType.VECTOR)
    return vectors >= 1


def social_auth_row_confidence(node: CleanDesignTreeNode) -> float:
    """Score how likely a node is a horizontal social sign-in row using layout only.

    Does not read ``name`` or ``text`` — only structure, types, and bounding boxes.

    Args:
        node: Candidate node from the clean design tree.

    Returns:
        Confidence in ``[0, 1]``.
    """
    if node.type not in {NodeType.ROW, NodeType.STACK}:
        return 0.0
    width, height = _child_extent(node)
    if width is None or height is None:
        return 0.0
    if height < _SOCIAL_ROW_MIN_HEIGHT or height > _SOCIAL_ROW_MAX_HEIGHT:
        return 0.0
    if width < _SOCIAL_ROW_MIN_WIDTH:
        return 0.0
    if len(node.children) < 2:
        return 0.0

    icons = 0
    labels = 0
    for child in node.children:
        c_w, c_h = _child_extent(child)
        if child.type == NodeType.VECTOR and c_w is not None and c_h is not None:
            if c_w <= _ICON_MAX_SIZE and c_h <= _ICON_MAX_SIZE:
                icons += 1
        elif _compact_icon_stack(child):
            icons += 1
        if child.type == NodeType.TEXT:
            label_width = c_w if c_w is not None else width
            if label_width >= _LABEL_MIN_WIDTH:
                labels += 1
        if child.type == NodeType.STACK:
            stack_w, _ = _child_extent(child)
            text_children = [item for item in child.children if item.type == NodeType.TEXT]
            for nested in text_children:
                n_w, _ = _child_extent(nested)
                label_width = n_w if n_w is not None else stack_w
                if label_width is not None and label_width >= _LABEL_MIN_WIDTH:
                    labels += 1
                    break

    if icons < 1 or labels < 1:
        return 0.0

    score = 0.55
    if node.type == NodeType.ROW:
        score += 0.15
    if len(node.children) <= 4:
        score += 0.1
    if icons == 1 and labels == 1:
        score += 0.2
    return min(1.0, score)


def social_auth_icon_button_confidence(node: CleanDesignTreeNode) -> float:
    """Score compact icon-only social login variant rows using layout only."""
    if node.type not in {NodeType.ROW, NodeType.BUTTON, NodeType.STACK}:
        return 0.0
    width, height = _child_extent(node)
    if width is None or height is None:
        return 0.0
    if not (
        _SOCIAL_ICON_BUTTON_MIN_HEIGHT <= float(height) <= _SOCIAL_ICON_BUTTON_MAX_HEIGHT
    ):
        return 0.0
    if not (
        _SOCIAL_ICON_BUTTON_MIN_WIDTH <= float(width) <= _SOCIAL_ICON_BUTTON_MAX_WIDTH
    ):
        return 0.0
    icons = 0
    labels = 0
    for child in node.children:
        c_w, c_h = _child_extent(child)
        if child.type == NodeType.TEXT:
            label_width = c_w if c_w is not None else width
            if label_width is not None and label_width >= _LABEL_MIN_WIDTH:
                labels += 1
        elif child.type == NodeType.VECTOR and c_w is not None and c_h is not None:
            if c_w <= _ICON_MAX_SIZE and c_h <= _ICON_MAX_SIZE:
                icons += 1
        elif _compact_icon_stack(child):
            icons += 1
        elif child.type == NodeType.STACK:
            vector_children = [
                item for item in child.children if item.type == NodeType.VECTOR
            ]
            if vector_children and not any(item.type == NodeType.TEXT for item in child.children):
                icons += 1
    if icons < 1 or labels > 0:
        return 0.0
    if node.style.background_color is not None or node.style.border_color is not None:
        return 0.85
    return 0.7


def auth_button_confidence(node: CleanDesignTreeNode) -> float:
    """Score whether a node is a full-width auth control (``NodeType.BUTTON`` + bbox only).

    Args:
        node: Candidate from the clean design tree.

    Returns:
        Confidence in ``[0, 1]``.
    """
    if node.type != NodeType.BUTTON:
        return 0.0
    width, height = _child_extent(node)
    if width is None or height is None:
        return 0.0
    if height < _SOCIAL_ROW_MIN_HEIGHT or height > _SOCIAL_ROW_MAX_HEIGHT:
        return 0.0
    if width < _SOCIAL_ROW_MIN_WIDTH:
        return 0.0
    return 1.0


def find_social_auth_row(root: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the highest-confidence social auth row under ``root``.

    Args:
        root: Screen root node.

    Returns:
        Best matching row node, or ``None``.
    """
    best: CleanDesignTreeNode | None = None
    best_score = 0.0

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal best, best_score
        score = social_auth_row_confidence(node)
        if score > best_score:
            best_score = score
            best = node
        for child in node.children:
            walk(child)

    walk(root)
    if best_score < 0.7:
        return None
    return best


_GEOMETRY_CONFIDENCE_THRESHOLD = 0.7
_SOCIAL_ROW_SOURCE_TYPES = frozenset({NodeType.ROW, NodeType.STACK, NodeType.CONTAINER})


def find_node_by_id(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    """Return the first node with ``id`` under ``root``.

    Args:
        root: Tree root.
        node_id: Figma node id.

    Returns:
        Matching node or ``None``.
    """
    if root.id == node_id:
        return root
    for child in root.children:
        found = find_node_by_id(child, node_id)
        if found is not None:
            return found
    return None


def enrich_clean_tree_from_geometry(root: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Promote geometry-detected social auth rows to ``NodeType.BUTTON``.

    Args:
        root: Parsed clean design tree (mutated in place).

    Returns:
        The same root instance for chaining.
    """

    def walk(node: CleanDesignTreeNode) -> None:
        if (
            node.type in _SOCIAL_ROW_SOURCE_TYPES
            and social_auth_row_confidence(node) >= _GEOMETRY_CONFIDENCE_THRESHOLD
        ):
            node.type = NodeType.BUTTON
        for child in node.children:
            walk(child)

    walk(root)
    return root


@dataclass(frozen=True)
class TransformContext:
    """Affine transform extracted from a Figma node ``relativeTransform`` matrix."""

    rotation_rad: float | None = None
    translate_x: float = 0.0
    translate_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0


def transform_context_from_figma_node(raw: dict[str, Any]) -> TransformContext | None:
    """Parse Figma's 2×3 ``relativeTransform`` into a ``TransformContext``.

    Args:
        raw: Raw Figma node JSON.

    Returns:
        Parsed transform, or ``None`` when the matrix is absent or invalid.
    """
    matrix = raw.get("relativeTransform")
    if not isinstance(matrix, list) or len(matrix) < 2:
        return None
    try:
        row0 = matrix[0]
        row1 = matrix[1]
        a, c, tx = float(row0[0]), float(row0[1]), float(row0[2])
        b, d, ty = float(row1[0]), float(row1[1]), float(row1[2])
    except (IndexError, TypeError, ValueError):
        return None
    rotation_rad = math.atan2(b, a)
    scale_x = math.hypot(a, b)
    scale_y = math.hypot(c, d)
    if scale_x < 1e-6 and scale_y < 1e-6:
        return None
    return TransformContext(
        rotation_rad=rotation_rad,
        translate_x=tx,
        translate_y=ty,
        scale_x=scale_x,
        scale_y=scale_y,
    )


def rotation_degrees_from_figma_node(raw: dict[str, Any]) -> float | None:
    """Return rotation in degrees from explicit field or ``relativeTransform``."""
    if raw.get("rotation") is not None:
        return float(raw["rotation"])
    ctx = transform_context_from_figma_node(raw)
    if ctx is None or ctx.rotation_rad is None:
        return None
    return math.degrees(ctx.rotation_rad)


def rotation_radians_from_figma_node(raw: dict[str, Any]) -> float | None:
    """Return rotation in radians from explicit degrees field or ``relativeTransform``."""
    if raw.get("rotation") is not None:
        return math.radians(float(raw["rotation"]))
    ctx = transform_context_from_figma_node(raw)
    if ctx is None or ctx.rotation_rad is None:
        return None
    return ctx.rotation_rad
