"""Node detection predicates for ambient background classification."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _collect_all_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_collect_all_nodes(child))
    return nodes


def _subtree_has_interactive_ui(node: CleanDesignTreeNode) -> bool:
    """True when the subtree contains interactive node types (semantic, not copy)."""
    for current in _collect_all_nodes(node):
        if current.type in {
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
        }:
            return True
    return False


def is_screen_wallpaper_node(node: CleanDesignTreeNode, root: CleanDesignTreeNode) -> bool:
    """Oversized collapsed illustration that must render as cover wallpaper only."""
    if not node.render_boundary or not node.vector_asset_key:
        return False
    screen_width = float(root.sizing.width or 0.0)
    screen_height = float(root.sizing.height or 0.0)
    if screen_width <= 0.0 or screen_height <= 0.0:
        return False
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    if width <= 0.0 or height <= 0.0:
        return False
    screen_area = screen_width * screen_height
    node_area = width * height
    return (
        node_area > screen_area * 1.05
        or width > screen_width * 1.08
        or height > screen_height * 1.08
    )


def _is_navigation_chrome_stack(node: CleanDesignTreeNode) -> bool:
    """Small icon-only stacks (back/close) are controls, not wallpaper."""
    if node.type != NodeType.STACK or node.stack_placement is None:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width > 96 or height > 96 or width < 20 or height < 20:
        return False
    if any(
        descendant.type in {NodeType.BUTTON, NodeType.INPUT, NodeType.TEXT}
        for descendant in _collect_all_nodes(node)
    ):
        return False
    name = (node.name or "").lower()
    if any(token in name for token in ("back", "close", "nav", "arrow")):
        return True
    top = node.stack_placement.top if node.stack_placement.top is not None else node.offset_y
    vector_children = [
        child for child in node.children if child.type == NodeType.VECTOR and child.vector_asset_key
    ]
    return top is not None and top < 120 and bool(vector_children)


def _has_playback_timeline_markers(node: CleanDesignTreeNode) -> bool:
    """True when a subtree contains short ``MM:SS`` duration labels."""
    for descendant in _collect_all_nodes(node):
        if descendant.type != NodeType.TEXT or not descendant.text:
            continue
        label = descendant.text.strip()
        if ":" in label and len(label) <= 8:
            return True
    return False


def _has_decorative_vector_name(node: CleanDesignTreeNode) -> bool:
    name = (node.name or "").strip().lower()
    return name.startswith(("ellipse", "blob", "shape"))


def _is_playback_chrome_stack(node: CleanDesignTreeNode) -> bool:
    """Player transport rows (play/pause, skip clusters) are foreground controls."""
    from figma_flutter_agent.parser.interaction import (
        layout_fact_play_pause_control_stack,
        layout_fact_skip_control_stack,
    )

    if node.type != NodeType.STACK:
        return False
    for descendant in _collect_all_nodes(node):
        if layout_fact_play_pause_control_stack(descendant):
            return True
        if descendant.cluster_id and layout_fact_skip_control_stack(descendant):
            return True
    return False


def _is_ambient_background_child(node: CleanDesignTreeNode) -> bool:
    if _subtree_has_interactive_ui(node):
        return False
    if any(descendant.type == NodeType.TEXT for descendant in _collect_all_nodes(node)):
        return False
    if any(descendant.accessibility_label for descendant in _collect_all_nodes(node)) and not (
        node.type in {NodeType.VECTOR, NodeType.IMAGE} and _has_decorative_vector_name(node)
    ):
        return False
    if _is_playback_chrome_stack(node):
        return False
    if _has_playback_timeline_markers(node):
        return False
    if _is_navigation_chrome_stack(node):
        return False
    if node.stack_placement is None:
        return False
    if node.type == NodeType.VECTOR and node.vector_asset_key:
        return True
    if node.type == NodeType.IMAGE and node.image_asset_key:
        return True
    if node.type == NodeType.STACK:
        return any(
            descendant.type in {NodeType.VECTOR, NodeType.IMAGE}
            and (descendant.vector_asset_key or descendant.image_asset_key)
            for descendant in _collect_all_nodes(node)
        )
    return False
