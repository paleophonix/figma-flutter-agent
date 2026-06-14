"""Detect multicolor icon groups that should export as a single SVG."""

from __future__ import annotations

import re
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

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
_MAX_COMPOSITE_ICON_WIDTH = 64.0
_MAX_COMPOSITE_ICON_HEIGHT = 64.0
_MIN_COMPOSITE_ICON_VECTORS = 2
_FIGMA_CONTAINER_TYPES = frozenset({"FRAME", "GROUP", "COMPONENT", "INSTANCE"})
_ICON_HOST_WORDS = frozenset({"icon", "chevron", "star", "arrow", "nav", "rating"})


def _icon_host_name_tokens(name: str) -> set[str]:
    """Return normalized name tokens for interactive icon-host detection."""
    return set(re.findall(r"[a-z0-9]+", (name or "").lower()))


def _name_signals_icon_host(name: str) -> bool:
    """Return True when a layer name denotes a nav/rating/icon host (not ``feedback``)."""
    tokens = _icon_host_name_tokens(name)
    if tokens & _ICON_HOST_WORDS:
        return True
    return any(token.startswith(("star", "chevron", "arrow")) for token in tokens)


def _figma_bbox_size(node: dict[str, Any]) -> tuple[float | None, float | None]:
    box = node.get("absoluteBoundingBox") or {}
    width = box.get("width")
    height = box.get("height")
    return (
        float(width) if width is not None else None,
        float(height) if height is not None else None,
    )


def is_figma_composite_icon_node(node: dict[str, Any]) -> bool:
    """True when a Figma frame/group is a small multicolor vector icon (e.g. Google G)."""
    node_type = node.get("type")
    if node_type not in {"FRAME", "GROUP", "COMPONENT", "INSTANCE"}:
        return False
    children = [child for child in (node.get("children") or []) if child.get("visible") is not False]
    vector_children = [child for child in children if child.get("type") in _FIGMA_VECTOR_TYPES]
    if len(vector_children) < _MIN_COMPOSITE_ICON_VECTORS:
        return False
    width, height = _figma_bbox_size(node)
    if width is None or height is None:
        return False
    return width <= _MAX_COMPOSITE_ICON_WIDTH and height <= _MAX_COMPOSITE_ICON_HEIGHT


def _is_figma_button_like_node(node: dict[str, Any]) -> bool:
    name = str(node.get("name") or "").lower()
    if "button" in name or "btn" in name:
        return True
    node_type = str(node.get("type") or "")
    return node_type in {"INSTANCE", "COMPONENT"} and ("button" in name or "btn" in name)


def _count_figma_vectors(node: dict[str, Any]) -> int:
    total = 0
    node_type = node.get("type")
    if node_type in _FIGMA_VECTOR_TYPES:
        total += 1
    for child in node.get("children") or []:
        if child.get("visible") is False:
            continue
        total += _count_figma_vectors(child)
    return total


def _is_figma_button_icon_group(node: dict[str, Any]) -> bool:
    """Small icon container inside an interactive host (e.g. chevron, star glyph)."""
    if node.get("type") not in _FIGMA_CONTAINER_TYPES:
        return False
    width, height = _figma_bbox_size(node)
    if width is None or height is None:
        return False
    if width > _MAX_COMPOSITE_ICON_WIDTH or height > _MAX_COMPOSITE_ICON_HEIGHT:
        return False
    if _count_figma_vectors(node) < 1:
        return False
    name = str(node.get("name") or "")
    if _name_signals_icon_host(name) or _icon_host_name_tokens(name) & {"svg", "vector"}:
        return True
    return width <= 32.0 and height <= 32.0


def _mark_composite_icon_descendants_skip(node: dict[str, Any], skip: set[str]) -> None:
    """Record vector descendants to skip when exporting the parent icon group."""
    node_id = node.get("id")
    if isinstance(node_id, str):
        skip.add(node_id)
    for child in node.get("children") or []:
        if child.get("visible") is False:
            continue
        _mark_composite_icon_descendants_skip(child, skip)


def _is_figma_interactive_icon_host(node: dict[str, Any]) -> bool:
    """Return True for buttons and compact nav/rating hosts that wrap icon exports."""
    if _is_figma_button_like_node(node):
        return True
    node_type = str(node.get("type") or "")
    if node_type not in {"INSTANCE", "COMPONENT", "FRAME", "GROUP"}:
        return False
    return _name_signals_icon_host(str(node.get("name") or ""))


def _collect_button_icon_groups_under(node: dict[str, Any], parents: set[str], skip: set[str]) -> None:
    if _is_figma_interactive_icon_host(node):
        for child in node.get("children") or []:
            if child.get("visible") is False:
                continue
            if not _is_figma_button_icon_group(child):
                continue
            child_id = child.get("id")
            if not isinstance(child_id, str):
                continue
            parents.add(child_id)
            for descendant in child.get("children") or []:
                if descendant.get("visible") is False:
                    continue
                _mark_composite_icon_descendants_skip(descendant, skip)
        return
    for child in node.get("children") or []:
        if child.get("visible") is False:
            continue
        _collect_button_icon_groups_under(child, parents, skip)


def collect_figma_composite_icon_groups(
    root: dict[str, Any],
) -> tuple[frozenset[str], frozenset[str]]:
    """Return parent node ids to export whole, and descendant ids to skip as separate icons."""
    parents: set[str] = set()
    skip: set[str] = set()

    def collect_descendants(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        if isinstance(node_id, str):
            skip.add(node_id)
        for child in node.get("children") or []:
            collect_descendants(child)

    def walk(node: dict[str, Any]) -> None:
        if node.get("visible") is False:
            return
        if is_figma_composite_icon_node(node):
            node_id = node.get("id")
            if isinstance(node_id, str):
                parents.add(node_id)
                for child in node.get("children") or []:
                    collect_descendants(child)
            return
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    _collect_button_icon_groups_under(root, parents, skip)
    return frozenset(parents), frozenset(skip)


def is_composite_icon_stack_shape(node: CleanDesignTreeNode) -> bool:
    """True when a stack matches a small multicolor icon group (with or without export)."""
    if node.type != NodeType.STACK:
        return False
    vectors = [child for child in node.children if child.type == NodeType.VECTOR]
    if len(vectors) < _MIN_COMPOSITE_ICON_VECTORS:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        placement = node.stack_placement
        if placement is not None:
            width = placement.width
            height = placement.height
    if width is None or height is None:
        return False
    return width <= _MAX_COMPOSITE_ICON_WIDTH and height <= _MAX_COMPOSITE_ICON_HEIGHT


def is_composite_icon_export_node(node: CleanDesignTreeNode) -> bool:
    """True when a clean-tree node should render as one exported SVG group."""
    if not is_composite_icon_stack_shape(node):
        return False
    return bool(node.vector_asset_key)
