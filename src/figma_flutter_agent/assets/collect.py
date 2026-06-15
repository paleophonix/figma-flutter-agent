"""Collect exportable Figma asset nodes."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.assets.models import AssetKind

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
_INTERACTIVE_ICON_HOST_TYPES = frozenset({"FRAME", "GROUP", "COMPONENT", "INSTANCE"})


def _figma_bbox_size(node: dict[str, Any]) -> tuple[float | None, float | None]:
    box = node.get("absoluteBoundingBox") or {}
    width = box.get("width")
    height = box.get("height")
    return (
        float(width) if width is not None else None,
        float(height) if height is not None else None,
    )


def _compact_vector_node(node: dict[str, Any]) -> bool:
    if node.get("type") not in _FIGMA_VECTOR_TYPES:
        return False
    width, height = _figma_bbox_size(node)
    if width is None or height is None:
        return False
    return width <= _MAX_COMPACT_VECTOR_PX and height <= _MAX_COMPACT_VECTOR_PX


def _is_interactive_icon_host(node: dict[str, Any]) -> bool:
    from figma_flutter_agent.assets.composite_icons import _is_figma_interactive_icon_host

    return _is_figma_interactive_icon_host(node)


def _collect_compact_vectors_under_excluded(
    node: dict[str, Any],
    items: list[tuple[str, str, AssetKind]],
    *,
    composite_skip: frozenset[str],
    seen: set[str],
    inside_interactive: bool = False,
) -> None:
    """Collect icon-sized vectors nested under interactive hosts in excluded subtrees."""
    if node.get("visible") is False:
        return
    node_id = node.get("id")
    host = inside_interactive or _is_interactive_icon_host(node)
    if (
        host
        and isinstance(node_id, str)
        and _compact_vector_node(node)
        and node_id not in composite_skip
        and node_id not in seen
    ):
        raw_name = node.get("name")
        name = str(raw_name) if raw_name is not None else node_id
        items.append((node_id, name, "icon"))
        seen.add(node_id)
    for child in node.get("children") or []:
        _collect_compact_vectors_under_excluded(
            child,
            items,
            composite_skip=composite_skip,
            seen=seen,
            inside_interactive=host,
        )


_ILLUSTRATION_HINTS = ("illustration", "hero", "banner", "artwork")


def classify_raster_kind(name: str, *, illustrations_enabled: bool) -> AssetKind:
    """Classify raster assets as standard images or illustrations."""
    if not illustrations_enabled:
        return "image"
    lowered = name.lower()
    if any(hint in lowered for hint in _ILLUSTRATION_HINTS):
        return "illustration"
    return "image"


def collect_exportable_nodes(
    root: dict[str, Any],
    *,
    illustrations_enabled: bool = True,
    exclude_node_ids: set[str] | None = None,
    flatten_exclude_node_ids: set[str] | None = None,
    render_boundary_node_ids: set[str] | None = None,
) -> list[tuple[str, str, AssetKind]]:
    """Collect exportable nodes as tuples of (id, name, kind)."""
    from figma_flutter_agent.assets.composite_icons import collect_figma_composite_icon_groups

    items: list[tuple[str, str, AssetKind]] = []
    excludes = exclude_node_ids or set()
    flatten_excludes = flatten_exclude_node_ids or set()
    boundary_ids = render_boundary_node_ids or set()
    composite_parents, composite_skip = collect_figma_composite_icon_groups(root)
    collected_ids: set[str] = set()

    def walk(node: dict[str, Any]) -> None:
        if node.get("visible") is False:
            return
        node_id = node.get("id")
        if not isinstance(node_id, str):
            return
        if node_id in flatten_excludes:
            for child in node.get("children") or []:
                walk(child)
            return
        if node_id in boundary_ids:
            raw_name = node.get("name")
            name = str(raw_name) if raw_name is not None else node_id
            if node_id not in collected_ids:
                items.append((node_id, name, "boundary_svg"))
                collected_ids.add(node_id)
            return
        if node_id in excludes:
            _collect_compact_vectors_under_excluded(
                node,
                items,
                composite_skip=composite_skip,
                seen=collected_ids,
            )
            for child in node.get("children") or []:
                walk(child)
            return
        node_type = node.get("type")
        raw_name = node.get("name")
        name = str(raw_name) if raw_name is not None else node_id
        if node_id in composite_parents:
            if node_id not in collected_ids:
                items.append((node_id, name, "icon"))
                collected_ids.add(node_id)
            return
        if node_id in composite_skip:
            return
        if node_type in {"VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "ELLIPSE", "POLYGON"}:
            if node_id in collected_ids:
                pass
            elif any(fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])):
                items.append(
                    (
                        node_id,
                        name,
                        classify_raster_kind(name, illustrations_enabled=illustrations_enabled),
                    )
                )
                collected_ids.add(node_id)
            else:
                items.append((node_id, name, "icon"))
                collected_ids.add(node_id)
        elif node_type == "RECTANGLE" and any(
            fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])
        ) or node_type == "ELLIPSE" and any(
            fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])
        ):
            if node_id not in collected_ids:
                items.append(
                    (
                        node_id,
                        name,
                        classify_raster_kind(name, illustrations_enabled=illustrations_enabled),
                    )
                )
                collected_ids.add(node_id)
        elif node.get("exportSettings"):
            if node_id not in collected_ids:
                if node_type in {"COMPONENT", "INSTANCE", "FRAME"}:
                    items.append((node_id, name, "icon"))
                else:
                    items.append(
                        (
                            node_id,
                            name,
                            classify_raster_kind(name, illustrations_enabled=illustrations_enabled),
                        )
                    )
                collected_ids.add(node_id)
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return items
