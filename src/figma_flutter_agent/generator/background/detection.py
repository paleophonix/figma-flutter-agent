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


def artboard_bleed_placement_exempt(
    child: CleanDesignTreeNode,
    parent: CleanDesignTreeNode,
    root: CleanDesignTreeNode,
) -> bool:
    """Root wallpaper/ambient children may bleed past the artboard without clamping."""
    if parent.id != root.id:
        return False
    if is_screen_wallpaper_node(child, root):
        return True
    return _is_ambient_background_child(child)


def root_has_wallpaper_overlay_slot(root: CleanDesignTreeNode) -> bool:
    """Return True when the artboard root must stay ``STACK`` for wallpaper/overlay slots.

    Veto root sectionize before raster binding: a ``render_boundary`` absolute slot
    must not be dropped when converting the artboard to a responsive ``COLUMN``.
    """
    if root.type != NodeType.STACK:
        return False
    for child in root.children:
        if is_screen_wallpaper_node(child, root):
            return True
        if child.render_boundary and (
            child.stack_placement is not None or child.layout_positioning == "ABSOLUTE"
        ):
            return True
        if is_decorative_absolute_background_overlay(child):
            return True
    return False


def is_screen_wallpaper_node(node: CleanDesignTreeNode, root: CleanDesignTreeNode) -> bool:
    """Oversized collapsed illustration that must render as cover wallpaper only."""
    if not node.render_boundary or not (node.vector_asset_key or node.image_asset_key):
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


def in_card_decorative_overlay_should_stay(
    parent: CleanDesignTreeNode,
    child: CleanDesignTreeNode,
) -> bool:
    """Keep decorative absolutes inside padded painted card stacks with inflow siblings."""
    if parent.type != NodeType.STACK:
        return False
    if not parent.style.background_color or parent.style.border_radius is None:
        return False
    padding = parent.padding
    if padding.top <= 0 and padding.bottom <= 0 and padding.left <= 0 and padding.right <= 0:
        return False
    for sibling in parent.children:
        if sibling.id == child.id:
            continue
        if is_decorative_absolute_background_overlay(sibling):
            continue
        if sibling.layout_positioning == "ABSOLUTE" or sibling.stack_placement is not None:
            continue
        return True
    return False


def is_bounded_interactive_surface_host(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack paints a bounded card/sheet around interactive inflow."""
    if node.type != NodeType.STACK:
        return False
    if not (node.style.background_color or node.style.border_radius is not None):
        return False
    padding = node.padding
    has_padding = padding.top > 0 or padding.bottom > 0 or padding.left > 0 or padding.right > 0
    if not has_padding:
        return False
    return _subtree_has_interactive_ui(node)


def is_decorative_absolute_background_overlay(node: CleanDesignTreeNode) -> bool:
    """Return True when an absolute stack child is non-interactive decorative chrome."""
    if node.stack_placement is None and node.layout_positioning != "ABSOLUTE":
        return False
    if _subtree_has_interactive_ui(node):
        return False
    if any(descendant.type == NodeType.TEXT for descendant in _collect_all_nodes(node)):
        return False
    if _is_playback_chrome_stack(node):
        return False
    if _has_playback_timeline_markers(node):
        return False
    if _is_navigation_chrome_stack(node):
        return False
    if node.render_boundary and node.flatten_figma_node_ids:
        return True
    return _is_ambient_background_child(node)


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
