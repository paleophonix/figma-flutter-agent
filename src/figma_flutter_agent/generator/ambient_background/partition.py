"""Tree partitioning into wallpaper vs foreground children."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .detection import _is_ambient_background_child, is_screen_wallpaper_node

_OPAQUE_SHELL_COLORS = frozenset(
    {
        "0xFFFFFFFF",
        "0xffffffff",
        "0xFFF2F3F7",
        "0xfff2f3f7",
        "0xFFFAF7F2",
        "0xfffaf7f2",
    },
)


def partition_wallpaper_foreground_tree(
    root: CleanDesignTreeNode,
) -> tuple[CleanDesignTreeNode, list[CleanDesignTreeNode], str | None]:
    """Split wallpaper vs UI and return a transparent foreground shell when needed.

    Returns:
        Tuple of ``(render_tree, wallpaper_children, material_background_color)``.
        ``material_background_color`` is ``None`` when the wallpaper layer provides
        the visible canvas fill behind semi-opaque vectors.
    """
    wallpaper_children, foreground_children = split_screen_wallpaper_children(root)
    if not foreground_children:
        foreground_children = list(root.children)
    probe = root.model_copy(update={"children": foreground_children})
    ambient = collect_ambient_background_children(probe)
    if ambient:
        ambient_ids = {item.id for item in ambient}
        wallpaper_children = [*wallpaper_children, *ambient]
        foreground_children = [
            child for child in foreground_children if child.id not in ambient_ids
        ]
        probe = probe.model_copy(update={"children": foreground_children})
    if not wallpaper_children:
        return root, [], root.style.background_color
    shell_color = root.style.background_color
    if shell_color in _OPAQUE_SHELL_COLORS:
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
