"""Discover top-level screen frames in a Figma file document."""

from __future__ import annotations

from typing import Any

_PAGE_TYPES = frozenset({"CANVAS", "PAGE"})
_SCREEN_TYPES = frozenset({"FRAME"})


def discover_page_level_frames(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Return frame nodes that represent screens (direct under page or section).

    Walks each page (``CANVAS`` / ``PAGE``), collects ``FRAME`` children and
    frames nested one level inside ``SECTION`` containers. Does not descend
    into frame subtrees (nested UI frames are ignored).

    Args:
        document: Figma ``DOCUMENT`` node from ``GET /v1/files/:key``.

    Returns:
        List of frame node dicts in document order.
    """
    frames: list[dict[str, Any]] = []

    def collect_from_container(container: dict[str, Any]) -> None:
        for child in container.get("children") or []:
            node_type = child.get("type")
            if node_type == "SECTION":
                collect_from_container(child)
                continue
            if node_type in _SCREEN_TYPES and child.get("visible", True) is not False:
                frames.append(child)

    for page in document.get("children") or []:
        if page.get("type") in _PAGE_TYPES:
            collect_from_container(page)
    return frames
