"""Explain why a Figma node is or is not collected for asset export."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.assets.collect import collect_exportable_nodes
from figma_flutter_agent.assets.composite_icons import collect_figma_composite_icon_groups
from figma_flutter_agent.assets.effects import index_figma_nodes, node_has_layer_blur

_FIGMA_VECTOR_TYPES = frozenset(
    {
        "VECTOR",
        "BOOLEAN_OPERATION",
        "STAR",
        "LINE",
        "ELLIPSE",
        "POLYGON",
    }
)
_MAX_COMPACT_VECTOR_PX = 48.0
_FIGMA_CONTAINER_CHILD_TYPES = frozenset({"GROUP", "FRAME", "COMPONENT", "INSTANCE"})


def node_has_direct_container_child(node: dict[str, Any]) -> bool:
    """Return True when a node has a visible GROUP/FRAME/COMPONENT/INSTANCE child."""
    for child in node.get("children") or []:
        if child.get("visible") is False:
            continue
        if child.get("type") in _FIGMA_CONTAINER_CHILD_TYPES:
            return True
    return False


def figma_images_api_skip_export(
    node: dict[str, Any],
    *,
    node_id: str,
    composite_parent_ids: frozenset[str],
) -> bool:
    """Return True when Figma Images API is unlikely to export this icon node.

    Covers layer-blur vectors and composite icon groups whose glyph sits inside a
    nested container (ellipse + inner group). The exporter recovers these at codegen
    via raster fallback or render-boundary flattening.
    """
    if node_has_layer_blur(node):
        return True
    return node_id in composite_parent_ids and node_has_direct_container_child(node)


def collect_raster_fallback_node_ids(
    figma_root: dict[str, Any],
    *,
    illustrations_enabled: bool = True,
    exclude_node_ids: set[str] | None = None,
    flatten_exclude_node_ids: set[str] | None = None,
    render_boundary_node_ids: set[str] | None = None,
) -> frozenset[str]:
    """Return icon node ids that should use PNG raster fallback instead of SVG export."""
    composite_parents, _composite_skip = collect_figma_composite_icon_groups(figma_root)
    figma_nodes = index_figma_nodes(figma_root)
    exportables = collect_exportable_nodes(
        figma_root,
        illustrations_enabled=illustrations_enabled,
        exclude_node_ids=exclude_node_ids,
        flatten_exclude_node_ids=flatten_exclude_node_ids,
        render_boundary_node_ids=render_boundary_node_ids,
    )
    return frozenset(
        node_id
        for node_id, _name, kind in exportables
        if kind == "icon"
        and figma_images_api_skip_export(
            figma_nodes.get(node_id, {}),
            node_id=node_id,
            composite_parent_ids=composite_parents,
        )
    )


def _figma_bbox_size(node: dict[str, Any]) -> tuple[float | None, float | None]:
    box = node.get("absoluteBoundingBox") or {}
    width = box.get("width")
    height = box.get("height")
    return (
        float(width) if width is not None else None,
        float(height) if height is not None else None,
    )


def _find_node_path(
    root: dict[str, Any],
    node_id: str,
) -> list[dict[str, Any]] | None:
    path: list[dict[str, Any]] = []

    def walk(node: dict[str, Any]) -> bool:
        path.append(node)
        if node.get("id") == node_id:
            return True
        for child in node.get("children") or []:
            if child.get("visible") is False:
                continue
            if walk(child):
                return True
        path.pop()
        return False

    if walk(root):
        return list(path)
    return None


def composite_skip_to_export_parent(root: dict[str, Any]) -> dict[str, str]:
    """Map composite-skipped vector ids to their exported parent icon group id."""
    parents, skip = collect_figma_composite_icon_groups(root)
    mapping: dict[str, str] = {}

    def walk(node: dict[str, Any], export_parent: str | None) -> None:
        node_id = node.get("id")
        current_parent = (
            node_id if isinstance(node_id, str) and node_id in parents else export_parent
        )
        if isinstance(node_id, str) and node_id in skip and current_parent is not None:
            mapping[node_id] = current_parent
        for child in node.get("children") or []:
            if child.get("visible") is False:
                continue
            walk(child, current_parent)

    walk(root, None)
    return mapping


def _compact_vector(node: dict[str, Any]) -> bool:
    if node.get("type") not in _FIGMA_VECTOR_TYPES:
        return False
    width, height = _figma_bbox_size(node)
    if width is None or height is None:
        return False
    return width <= _MAX_COMPACT_VECTOR_PX and height <= _MAX_COMPACT_VECTOR_PX


def explain_export_block(
    raw_root: dict[str, Any],
    node_id: str,
    *,
    flatten_excludes: set[str],
    excludes: set[str],
    boundary_ids: set[str],
) -> str:
    """Return a short gate label for why ``node_id`` is not exported as an icon.

    Args:
        raw_root: Raw Figma document subtree.
        node_id: Target node id.
        flatten_excludes: Flattened ids excluded from per-vector export.
        excludes: Screen-frame ids excluded from export collection.
        boundary_ids: Render-boundary ids exported as boundary SVG.

    Returns:
        ``exportable:<kind>`` when collected, otherwise a gate label.
    """
    path = _find_node_path(raw_root, node_id)
    if path is None:
        return "node_not_found"

    node = path[-1]
    if node.get("visible") is False:
        return "hidden"

    exportables = collect_exportable_nodes(
        raw_root,
        exclude_node_ids=set(excludes),
        flatten_exclude_node_ids=set(flatten_excludes),
        render_boundary_node_ids=set(boundary_ids),
    )
    for exported_id, _name, kind in exportables:
        if exported_id == node_id:
            return f"exportable:{kind}"

    composite_parents, composite_skip = collect_figma_composite_icon_groups(raw_root)
    if node_id in composite_skip:
        parent = composite_skip_to_export_parent(raw_root).get(node_id)
        if parent is not None:
            return f"composite_skip:parent={parent}"
        return "composite_skip"

    if node_id in flatten_excludes:
        return "flatten_exclude"

    if node_id in boundary_ids:
        return "boundary_export"

    if node_id in excludes:
        return "screen_frame_exclude"

    for ancestor in path[:-1]:
        ancestor_id = ancestor.get("id")
        if not isinstance(ancestor_id, str):
            continue
        if ancestor_id in flatten_excludes:
            return f"ancestor_flatten_exclude:{ancestor_id}"

    if node_id in composite_parents:
        return "composite_parent_pending"

    if _compact_vector(node):
        return "not_collected:compact_vector"

    return "not_collected"
