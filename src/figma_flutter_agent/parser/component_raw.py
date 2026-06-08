"""Raw Figma component geometry heuristics."""

from __future__ import annotations

from typing import Any

_GRAPHIC_LEAF_TYPES = frozenset({"VECTOR", "BOOLEAN_OPERATION", "LINE", "STAR", "POLYGON"})


def node_bbox_size(node: dict[str, Any]) -> tuple[float, float] | None:
    """Return ``(width, height)`` from Figma absolute bounds when present."""
    box = node.get("absoluteBoundingBox") or node.get("absoluteRenderBounds")
    if not isinstance(box, dict):
        return None
    width = box.get("width")
    height = box.get("height")
    if width is None or height is None:
        return None
    try:
        w = float(width)
        h = float(height)
    except (TypeError, ValueError):
        return None
    return w, h


def is_leaf_graphic_node(node: dict[str, Any]) -> bool:
    """Return True for atomic vector/mask layers without children."""
    raw_type = str(node.get("type") or "")
    if not is_raw_graphic_type(raw_type):
        return False
    children = node.get("children")
    return not children


def is_raw_graphic_type(raw_type: str) -> bool:
    return raw_type in _GRAPHIC_LEAF_TYPES


def _is_tab_peer_candidate(node: dict[str, Any]) -> bool:
    raw_type = str(node.get("type") or "")
    if raw_type == "TEXT":
        return bool(node.get("characters") or node.get("name"))
    if raw_type in {"FRAME", "INSTANCE", "COMPONENT", "GROUP"}:
        bbox = node_bbox_size(node)
        if bbox is not None and bbox[0] <= 96.0 and bbox[1] <= 72.0:
            return True
    return False


def count_horizontal_tab_peers(node: dict[str, Any], *, depth: int = 0) -> int:
    """Count sibling slots that resemble separate bottom-tab destinations."""
    if depth > 6:
        return 0
    children = node.get("children") or []
    if len(children) >= 2:
        peer_count = sum(1 for child in children if _is_tab_peer_candidate(child))
        if peer_count >= 2:
            return peer_count
    best = 0
    for child in children:
        best = max(best, count_horizontal_tab_peers(child, depth=depth + 1))
    return best


def count_raw_primary_buttons(node: dict[str, Any], *, depth: int = 0) -> int:
    """Count full-width CTA ``BUTTON`` frames nested under a footer host."""
    if depth > 8:
        return 0
    count = 0
    name = str(node.get("name") or "").lower()
    raw_type = str(node.get("type") or "")
    bbox = node_bbox_size(node)
    if (
        "button" in name
        and raw_type in {"FRAME", "INSTANCE", "COMPONENT"}
        and bbox is not None
        and bbox[0] >= 200.0
        and bbox[1] >= 40.0
    ):
        count += 1
    for child in node.get("children") or []:
        count += count_raw_primary_buttons(child, depth=depth + 1)
    return count


def raw_looks_like_bottom_cta_footer(node: dict[str, Any]) -> bool:
    """Short bottom sheet with a single primary button."""
    bbox = node_bbox_size(node)
    if bbox is None:
        return False
    width, height = bbox
    if width < 300.0 or not (60.0 <= height <= 160.0):
        return False
    tab_peers = count_horizontal_tab_peers(node)
    primary_buttons = count_raw_primary_buttons(node)
    return tab_peers < 2 and primary_buttons >= 1
