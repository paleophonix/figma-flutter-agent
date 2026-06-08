"""Collect exportable Figma asset nodes."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.assets.models import AssetKind

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

    def walk(node: dict[str, Any]) -> None:
        if node.get("visible") is False:
            return
        node_id = node.get("id")
        if not isinstance(node_id, str):
            return
        if node_id in flatten_excludes:
            return
        if node_id in boundary_ids:
            raw_name = node.get("name")
            name = str(raw_name) if raw_name is not None else node_id
            items.append((node_id, name, "boundary_svg"))
            return
        if node_id in excludes:
            for child in node.get("children") or []:
                walk(child)
            return
        node_type = node.get("type")
        raw_name = node.get("name")
        name = str(raw_name) if raw_name is not None else node_id
        if node_id in composite_parents:
            items.append((node_id, name, "icon"))
            return
        if node_id in composite_skip:
            return
        if node_type in {"VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "ELLIPSE", "POLYGON"}:
            if any(fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])):
                items.append(
                    (
                        node_id,
                        name,
                        classify_raster_kind(name, illustrations_enabled=illustrations_enabled),
                    )
                )
            else:
                items.append((node_id, name, "icon"))
        elif node_type == "RECTANGLE" and any(
            fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])
        ):
            items.append(
                (
                    node_id,
                    name,
                    classify_raster_kind(name, illustrations_enabled=illustrations_enabled),
                )
            )
        elif node.get("exportSettings"):
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
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return items
