"""Raw Figma node effect helpers for asset export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger


def index_figma_nodes(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index raw Figma nodes by id for export-time effect inspection."""
    nodes: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        if isinstance(node_id, str):
            nodes[node_id] = node
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return nodes


def node_has_blur_effect(node: dict[str, Any]) -> bool:
    """Return True when a raw Figma node declares a visible blur effect."""
    for effect in node.get("effects") or []:
        if effect.get("visible") is False:
            continue
        if effect.get("type") in {"LAYER_BLUR", "BACKGROUND_BLUR"}:
            radius = effect.get("radius")
            if radius is None or float(radius) > 0:
                return True
    return False


def node_has_layer_blur(node: dict[str, Any]) -> bool:
    """Return True when a raw Figma node declares a visible layer blur effect."""
    return node_has_blur_effect(node)


def write_webp_copy(png_path: Path) -> Path | None:
    """Convert a PNG asset to WebP when Pillow is available."""
    from figma_flutter_agent.assets.webp import webp_conversion_available

    if not webp_conversion_available():
        logger.warning("Pillow is not installed; skipping WebP conversion for {}", png_path.name)
        return None

    from PIL import Image

    webp_path = png_path.with_suffix(".webp")
    with Image.open(png_path) as image:
        image.save(webp_path, format="WEBP")
    return webp_path
