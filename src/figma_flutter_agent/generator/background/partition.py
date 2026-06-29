"""Tree partitioning into wallpaper vs foreground children."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import fill_luminance
from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import CleanDesignTreeNode, GeomRect, NodeType, StackPlacement

from .detection import (
    _is_ambient_background_child,
    in_card_decorative_overlay_should_stay,
    is_decorative_absolute_background_overlay,
    is_screen_wallpaper_node,
)


def _translate_hoisted_wallpaper_placement(
    child: CleanDesignTreeNode,
    former_parent: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Map nested wallpaper placement from a host stack into artboard coordinates."""
    parent_placement = former_parent.stack_placement
    parent_left = float(parent_placement.left or 0.0) if parent_placement is not None else 0.0
    parent_top = float(parent_placement.top or 0.0) if parent_placement is not None else 0.0
    frame = child.geometry_frame
    if frame is not None and frame.layout_rect is not None:
        child_left = float(frame.layout_rect.x or 0.0)
        child_top = float(frame.layout_rect.y or 0.0)
        child_width = float(frame.layout_rect.width or child.sizing.width or 0.0)
        child_height = float(frame.layout_rect.height or child.sizing.height or 0.0)
    elif child.stack_placement is not None:
        child_left = float(child.stack_placement.left or 0.0)
        child_top = float(child.stack_placement.top or 0.0)
        child_width = float(child.stack_placement.width or child.sizing.width or 0.0)
        child_height = float(child.stack_placement.height or child.sizing.height or 0.0)
    else:
        return child
    artboard_left = round_geometry(parent_left + child_left) or parent_left + child_left
    artboard_top = round_geometry(parent_top + child_top) or parent_top + child_top
    placement = child.stack_placement
    if placement is None:
        placement = StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=artboard_left,
            top=artboard_top,
            width=child_width if child_width > 0 else None,
            height=child_height if child_height > 0 else None,
        )
    else:
        placement = placement.model_copy(
            update={
                "horizontal": "LEFT",
                "vertical": "TOP",
                "left": artboard_left,
                "top": artboard_top,
            }
        )
    geometry = frame
    if geometry is not None and geometry.layout_rect is not None:
        layout_rect = geometry.layout_rect
        geometry = geometry.model_copy(
            update={
                "layout_rect": layout_rect.model_copy(
                    update={
                        "x": artboard_left,
                        "y": artboard_top,
                    }
                ),
                "placement_origin": GeomRect(x=artboard_left, y=artboard_top),
                "placement_aabb": GeomRect(
                    x=artboard_left,
                    y=artboard_top,
                    width=child_width if child_width > 0 else layout_rect.width,
                    height=child_height if child_height > 0 else layout_rect.height,
                ),
            }
        )
    return child.model_copy(update={"stack_placement": placement, "geometry_frame": geometry})


def extract_nested_decorative_backgrounds(
    root: CleanDesignTreeNode,
) -> tuple[CleanDesignTreeNode, list[CleanDesignTreeNode]]:
    """Hoist nested absolute decorative overlays into wallpaper candidates."""
    extracted: list[CleanDesignTreeNode] = []

    def prune(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        pruned_children: list[CleanDesignTreeNode] = []
        for child in node.children:
            if is_decorative_absolute_background_overlay(child):
                if in_card_decorative_overlay_should_stay(node, child):
                    pruned_children.append(prune(child))
                    continue
                extracted.append(_translate_hoisted_wallpaper_placement(child, node))
                continue
            pruned_children.append(prune(child))
        if pruned_children == node.children:
            return node
        return node.model_copy(update={"children": pruned_children})

    return prune(root), extracted


def _is_opaque_neutral_shell(color: str | None) -> bool:
    """Return True for bright neutral canvas fills that should not occlude wallpaper."""
    luminance = fill_luminance(color)
    return luminance is not None and luminance >= 0.88


def partition_wallpaper_foreground_tree(
    root: CleanDesignTreeNode,
) -> tuple[CleanDesignTreeNode, list[CleanDesignTreeNode], str | None]:
    """Split wallpaper vs UI and return a transparent foreground shell when needed.

    Returns:
        Tuple of ``(render_tree, wallpaper_children, material_background_color)``.
        ``material_background_color`` is ``None`` when the wallpaper layer provides
        the visible canvas fill behind semi-opaque vectors.
    """
    pruned_root, nested_decorative = extract_nested_decorative_backgrounds(root)
    wallpaper_children, foreground_children = split_screen_wallpaper_children(pruned_root)
    if nested_decorative:
        wallpaper_children = [*wallpaper_children, *nested_decorative]
    if not foreground_children:
        foreground_children = list(pruned_root.children)
    probe = pruned_root.model_copy(update={"children": foreground_children})
    ambient = collect_ambient_background_children(probe)
    if ambient:
        ambient_ids = {item.id for item in ambient}
        wallpaper_children = [*wallpaper_children, *ambient]
        foreground_children = [
            child for child in foreground_children if child.id not in ambient_ids
        ]
        probe = probe.model_copy(update={"children": foreground_children})
    if not wallpaper_children:
        return pruned_root, [], pruned_root.style.background_color
    shell_color = root.style.background_color
    if _is_opaque_neutral_shell(shell_color):
        probe = probe.model_copy(
            update={"style": probe.style.model_copy(update={"background_color": None})},
        )
        shell_color = None
    return probe, wallpaper_children, shell_color


def split_screen_wallpaper_children(
    root: CleanDesignTreeNode,
) -> tuple[list[CleanDesignTreeNode], list[CleanDesignTreeNode]]:
    """Partition root children into cover wallpaper vs foreground UI."""
    if root.type != NodeType.STACK:
        return [], []
    wallpaper: list[CleanDesignTreeNode] = []
    foreground: list[CleanDesignTreeNode] = []
    for child in root.children:
        if is_screen_wallpaper_node(child, root):
            wallpaper.append(child)
        else:
            foreground.append(child)
    return wallpaper, foreground


def split_wallpaper_emit_layers(
    root: CleanDesignTreeNode,
    wallpaper_children: list[CleanDesignTreeNode],
) -> tuple[list[CleanDesignTreeNode], list[CleanDesignTreeNode]]:
    """Split wallpaper into artboard-inline ambient vs host-level cover layers."""
    cover = [child for child in wallpaper_children if is_screen_wallpaper_node(child, root)]
    cover_ids = {child.id for child in cover}
    ambient = [child for child in wallpaper_children if child.id not in cover_ids]
    return ambient, cover


def collect_ambient_background_children(
    root: CleanDesignTreeNode,
) -> list[CleanDesignTreeNode]:
    """Return decorative root children that should sit behind the interactive canvas."""
    if root.type != NodeType.STACK:
        return []
    ambient: list[CleanDesignTreeNode] = []
    for child in root.children:
        if is_screen_wallpaper_node(child, root):
            continue
        if not _is_ambient_background_child(child):
            continue
        if in_card_decorative_overlay_should_stay(root, child):
            continue
        ambient.append(child)
    return ambient
