"""Published Figma style reference lookup."""

from __future__ import annotations

from typing import Any


def resolve_style_name(
    node: dict[str, Any],
    published_styles: dict[str, dict[str, Any]] | None,
) -> str | None:
    """Resolve a published Figma style name referenced by the node."""
    if not published_styles:
        return None
    style_refs = node.get("styles") or {}
    for style_id in style_refs.values():
        style_meta = published_styles.get(style_id)
        if style_meta and style_meta.get("name"):
            return str(style_meta["name"])
    return None


def collect_style_node_ids(published_styles: dict[str, dict[str, Any]]) -> list[str]:
    """Collect style definition node ids from published style metadata."""
    node_ids: list[str] = []
    seen: set[str] = set()
    for style_meta in published_styles.values():
        node_id = style_meta.get("node_id")
        if not node_id or node_id in seen:
            continue
        seen.add(str(node_id))
        node_ids.append(str(node_id))
    return node_ids


def build_style_paint_index(
    published_styles: dict[str, dict[str, Any]],
    style_nodes: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Map published style ids to their style definition node documents."""
    index: dict[str, dict[str, Any]] = {}
    for style_id, style_meta in published_styles.items():
        node_id = style_meta.get("node_id")
        if not node_id:
            continue
        style_node = style_nodes.get(str(node_id))
        if style_node is not None:
            index[style_id] = style_node
    return index


def style_reference_paints(
    node: dict[str, Any],
    style_paint_index: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Resolve published style paints referenced by a node."""
    if not style_paint_index:
        return None
    style_refs = node.get("styles") or {}
    for style_key in ("fill", "text", "stroke", "effect"):
        style_id = style_refs.get(style_key)
        if not style_id:
            continue
        style_node = style_paint_index.get(style_id)
        if style_node is not None:
            return style_node
    return None
