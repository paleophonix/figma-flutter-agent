"""Heuristics that decide when a subtree can become a render boundary."""

from __future__ import annotations

from figma_flutter_agent.parser.interaction import (
    looks_like_back_nav_stack,
    looks_like_compact_icon_action_stack,
    looks_like_media_controls_stack,
    looks_like_password_field_stack,
    looks_like_play_pause_control_stack,
    looks_like_skip_control_stack,
    looks_like_wheel_time_picker_stack,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.semantics.signals.chip_anatomy import is_compact_chip_stack
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_MIN_CHILD_COUNT = 6
_MIN_VECTOR_COUNT = 4
_MIN_BOUNDARY_AREA = 8_000.0
_MAX_COMPACT_BOUNDARY_WIDTH = 64.0
_MAX_COMPACT_BOUNDARY_HEIGHT = 64.0
_MAX_SIGNIFICANT_TEXT_LEN = 32

_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
        NodeType.CAROUSEL,
    }
)
_VISUAL_LEAF_TYPES = frozenset({NodeType.VECTOR, NodeType.IMAGE})
_LAYOUT_CONTAINER_TYPES = frozenset(
    {NodeType.STACK, NodeType.CONTAINER, NodeType.COLUMN, NodeType.ROW}
)


def _node_area(node: CleanDesignTreeNode) -> float:
    placement = node.stack_placement
    width = (placement.width if placement is not None else None) or node.sizing.width
    height = (placement.height if placement is not None else None) or node.sizing.height
    if width is None or height is None:
        return 0.0
    return float(width) * float(height)


def _is_compact_boundary(node: CleanDesignTreeNode) -> bool:
    placement = node.stack_placement
    width = (placement.width if placement is not None else None) or node.sizing.width
    height = (placement.height if placement is not None else None) or node.sizing.height
    if width is None or height is None:
        return False
    return (
        float(width) <= _MAX_COMPACT_BOUNDARY_WIDTH
        and float(height) <= _MAX_COMPACT_BOUNDARY_HEIGHT
    )


def _count_vectors(node: CleanDesignTreeNode) -> int:
    total = 0
    if node.type in _VISUAL_LEAF_TYPES:
        total += 1
    if node.vector_asset_key or node.image_asset_key:
        total += 1
    for child in node.children:
        total += _count_vectors(child)
    return total


def _count_decorative_leaves(node: CleanDesignTreeNode) -> int:
    if node.type in _VISUAL_LEAF_TYPES:
        return 1
    if node.vector_asset_key or node.image_asset_key:
        return 1
    if not node.children:
        if node.type == NodeType.CONTAINER and (
            node.style.background_color
            or node.style.border_color
            or node.style.gradient is not None
        ):
            return 1
        return 0
    return sum(_count_decorative_leaves(child) for child in node.children)


def _count_children(node: CleanDesignTreeNode) -> int:
    total = len(node.children)
    for child in node.children:
        total += _count_children(child)
    return total


def _has_interactive_semantics(node: CleanDesignTreeNode) -> bool:
    if node.type in _INTERACTIVE_TYPES:
        return True
    if node.extracted_widget_ref:
        return True
    if node.type == NodeType.STACK and stack_interaction_kind(node) is not None:
        return True
    if looks_like_password_field_stack(node):
        return True
    if looks_like_media_controls_stack(node):
        return True
    if looks_like_play_pause_control_stack(node):
        return True
    if looks_like_wheel_time_picker_stack(node):
        return True
    if is_compact_chip_stack(node):
        return True
    return False


def _has_significant_copy(node: CleanDesignTreeNode) -> bool:
    if node.type == NodeType.TEXT and node.text:
        return len(node.text.strip()) > _MAX_SIGNIFICANT_TEXT_LEN
    return any(_has_significant_copy(child) for child in node.children)


def _is_illustration_card(node: CleanDesignTreeNode) -> bool:
    if _node_area(node) < 30_000.0:
        return False
    has_copy = any(
        child.type == NodeType.TEXT and child.text for child in node.children
    ) or any(_is_illustration_card(child) for child in node.children)
    if not has_copy:
        return False
    return _count_decorative_leaves(node) >= 2


def _is_visual_only_subtree(node: CleanDesignTreeNode) -> bool:
    if _has_interactive_semantics(node):
        return False
    if node.type in _VISUAL_LEAF_TYPES:
        return True
    if node.type == NodeType.TEXT:
        return True
    if node.type == NodeType.BUTTON:
        return True
    if node.type not in _LAYOUT_CONTAINER_TYPES:
        return False
    if not node.children:
        return True
    return all(_is_visual_only_subtree(child) for child in node.children)


def _is_absolute_graphic_container(node: CleanDesignTreeNode) -> bool:
    if node.type not in {NodeType.STACK, NodeType.CONTAINER}:
        return False
    if node.stack_placement is None and node.layout_positioning != "ABSOLUTE":
        return False
    return True


def _boundary_denied(
    node: CleanDesignTreeNode,
    *,
    parent: CleanDesignTreeNode | None,
    screen_root: CleanDesignTreeNode,
) -> bool:
    if node.render_boundary:
        return True
    if (
        parent is screen_root
        and _has_significant_copy(node)
        and not _is_illustration_card(node)
    ):
        return True
    if _has_interactive_semantics(node) and not _is_illustration_card(node):
        return True
    return False


def _subtree_has_player_or_chrome_controls(node: CleanDesignTreeNode) -> bool:
    """Return True when collapsing would remove interactive player chrome."""
    if looks_like_play_pause_control_stack(node):
        return True
    if looks_like_skip_control_stack(node):
        return True
    if looks_like_wheel_time_picker_stack(node):
        return True
    if is_compact_chip_stack(node):
        return True
    if looks_like_media_controls_stack(node):
        return True
    if looks_like_back_nav_stack(node) or looks_like_compact_icon_action_stack(node):
        return True
    return any(_subtree_has_player_or_chrome_controls(child) for child in node.children)


def should_collapse_boundary(
    node: CleanDesignTreeNode,
    *,
    parent: CleanDesignTreeNode | None,
    screen_root: CleanDesignTreeNode,
) -> bool:
    if not _is_absolute_graphic_container(node):
        return False
    if _subtree_has_player_or_chrome_controls(node):
        return False
    if _boundary_denied(node, parent=parent, screen_root=screen_root):
        return False
    if not _is_visual_only_subtree(node):
        return False
    if _is_compact_boundary(node):
        return False
    area = _node_area(node)
    min_child_count = _MIN_CHILD_COUNT
    min_visual_mass = _MIN_VECTOR_COUNT
    if area >= 150_000.0:
        min_child_count = 2
        min_visual_mass = 2
    decorative_leaves = _count_decorative_leaves(node)
    vector_count = _count_vectors(node)
    visual_mass = max(decorative_leaves, vector_count)
    if visual_mass < min_visual_mass:
        return False
    child_count = _count_children(node)
    if child_count < min_child_count:
        return False
    if area < _MIN_BOUNDARY_AREA and visual_mass < min_child_count:
        return False
    return True
