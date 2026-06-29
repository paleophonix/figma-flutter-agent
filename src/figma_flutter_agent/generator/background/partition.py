"""Tree partitioning into wallpaper vs foreground children."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import fill_luminance
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .detection import (
    _is_ambient_background_child,
    is_decorative_absolute_background_overlay,
    is_screen_wallpaper_node,
)


def extract_nested_decorative_backgrounds(
    root: CleanDesignTreeNode,
) -> tuple[CleanDesignTreeNode, list[CleanDesignTreeNode]]:
    """Hoist nested absolute decorative overlays into wallpaper candidates."""
    extracted: list[CleanDesignTreeNode] = []

    def prune(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        pruned_children: list[CleanDesignTreeNode] = []
        for child in node.children:
            if is_decorative_absolute_background_overlay(child):
                extracted.append(child)
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
        ambient.append(child)
    return ambient
