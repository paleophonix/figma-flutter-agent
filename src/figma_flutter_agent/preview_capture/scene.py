"""Convert clean design trees into browser preview scenes."""

from __future__ import annotations

import math
from pathlib import Path

from figma_flutter_agent.parser.css import argb_hex_to_css_rgba
from figma_flutter_agent.preview_capture.models import PreviewNode, PreviewScene
from figma_flutter_agent.schemas.geometry import GeometryFrame, GeomRect
from figma_flutter_agent.schemas.tree import CleanDesignTreeNode
from figma_flutter_agent.schemas.types import NodeType

_ASSET_SEARCH_DIRS = (
    "assets/images",
    "assets/icons",
    "assets/illustrations",
    "assets",
)


def preview_css_color(value: str | None) -> str | None:
    """Map clean-tree color tokens to CSS colors understood by the HTML renderer."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if trimmed.startswith(("rgba(", "rgb(", "#")):
        return trimmed
    if trimmed.startswith(("0x", "0X")):
        return argb_hex_to_css_rgba(trimmed)
    return trimmed


def _rect_from_geometry(frame: GeometryFrame | None) -> GeomRect | None:
    if frame is None:
        return None
    if frame.paint_rect is not None and frame.paint_rect.width > 0 and frame.paint_rect.height > 0:
        return frame.paint_rect
    if frame.world_aabb.width > 0 and frame.world_aabb.height > 0:
        return frame.world_aabb
    if frame.placement_aabb is not None and frame.placement_aabb.width > 0:
        return frame.placement_aabb
    return None


def _bounds_for_node(node: CleanDesignTreeNode) -> GeomRect:
    geom = _rect_from_geometry(node.geometry_frame)
    if geom is not None:
        return geom
    placement = node.stack_placement
    if placement is not None:
        width = placement.width if placement.width is not None else node.sizing.width
        height = placement.height if placement.height is not None else node.sizing.height
        return GeomRect(
            x=placement.left + node.offset_x,
            y=placement.top + node.offset_y,
            width=float(width or 0),
            height=float(height or 0),
        )
    width = node.sizing.width if node.sizing.width is not None else 0.0
    height = node.sizing.height if node.sizing.height is not None else 0.0
    return GeomRect(x=node.offset_x, y=node.offset_y, width=float(width), height=float(height))


def _artboard_background(tree: CleanDesignTreeNode) -> str:
    if tree.style.background_color:
        return preview_css_color(tree.style.background_color) or "#FFFFFF"
    return "#FFFFFF"


def _artboard_size(tree: CleanDesignTreeNode) -> tuple[int, int]:
    width = tree.sizing.width
    height = tree.sizing.height
    surface_width = max(int(width), 1) if isinstance(width, (int, float)) and width > 0 else 390
    surface_height = max(int(height), 1) if isinstance(height, (int, float)) and height > 0 else 844
    return surface_width, surface_height


def _resolve_asset_src(
    asset_key: str | None,
    *,
    project_dir: Path | None,
) -> str | None:
    if not asset_key:
        return None
    if asset_key.startswith(("http://", "https://", "data:", "file:")):
        return asset_key
    if project_dir is None:
        return asset_key
    normalized_key = asset_key.replace("\\", "/").lstrip("/")
    direct = project_dir / normalized_key
    if direct.is_file():
        return direct.resolve().as_uri()
    basename = Path(normalized_key).name
    for sub in _ASSET_SEARCH_DIRS:
        candidate = project_dir / sub / basename
        if candidate.is_file():
            return candidate.resolve().as_uri()
        candidate = project_dir / sub / normalized_key
        if candidate.is_file():
            return candidate.resolve().as_uri()
    return asset_key


def _preview_coordinate_origin(tree: CleanDesignTreeNode) -> tuple[float, float]:
    """Map Figma world-space paint bounds onto a 0,0 artboard for HTML preview."""
    min_x = math.inf
    min_y = math.inf
    stack = list(tree.children)
    while stack:
        current = stack.pop()
        bounds = _bounds_for_node(current)
        if bounds.width > 0 and bounds.height > 0:
            min_x = min(min_x, bounds.x)
            min_y = min(min_y, bounds.y)
        stack.extend(current.children)
    if min_x is math.inf:
        return 0.0, 0.0
    return min_x, min_y


def _append_node_layers(
    node: CleanDesignTreeNode,
    *,
    nodes: list[PreviewNode],
    project_dir: Path | None,
    origin_x: float,
    origin_y: float,
) -> None:
    bounds = _bounds_for_node(node)
    if bounds.width <= 0 or bounds.height <= 0:
        for child in node.children:
            _append_node_layers(
                child,
                nodes=nodes,
                project_dir=project_dir,
                origin_x=origin_x,
                origin_y=origin_y,
            )
        return

    opacity = node.style.opacity
    local_x = bounds.x - origin_x
    local_y = bounds.y - origin_y
    if node.type is NodeType.TEXT and node.text:
        nodes.append(
            PreviewNode(
                id=node.id,
                type="text",
                x=local_x,
                y=local_y,
                width=bounds.width,
                height=bounds.height,
                text=node.text,
                font_size=node.style.font_size,
                font_family=node.style.font_family,
                font_weight=node.style.font_weight,
                color=preview_css_color(node.style.text_color),
                line_height=node.style.line_height,
                opacity=opacity,
            ),
        )
    elif node.image_asset_key or node.vector_asset_key:
        image_src = _resolve_asset_src(
            node.image_asset_key or node.vector_asset_key,
            project_dir=project_dir,
        )
        nodes.append(
            PreviewNode(
                id=node.id,
                type="image",
                x=local_x,
                y=local_y,
                width=bounds.width,
                height=bounds.height,
                image_src=image_src,
                opacity=opacity,
            ),
        )
    elif node.style.background_color or node.style.border_color or node.style.has_stroke:
        nodes.append(
            PreviewNode(
                id=node.id,
                type="rect",
                x=local_x,
                y=local_y,
                width=bounds.width,
                height=bounds.height,
                fill=preview_css_color(node.style.background_color),
                border_radius=node.style.border_radius,
                border_width=node.style.border_width,
                border_color=preview_css_color(node.style.border_color),
                opacity=opacity,
            ),
        )

    for child in node.children:
        _append_node_layers(
            child,
            nodes=nodes,
            project_dir=project_dir,
            origin_x=origin_x,
            origin_y=origin_y,
        )


def preview_scene_from_clean_tree(
    tree: CleanDesignTreeNode,
    *,
    project_dir: Path | None = None,
) -> PreviewScene:
    """Build a factual preview scene from a clean design tree.

    Args:
        tree: Parsed clean design tree root.
        project_dir: Optional Flutter project root for on-disk asset resolution.

    Returns:
        Preview scene with absolute nodes in paint order.
    """
    width, height = _artboard_size(tree)
    origin_x, origin_y = _preview_coordinate_origin(tree)
    nodes: list[PreviewNode] = []
    nodes.append(
        PreviewNode(
            id=f"{tree.id}:artboard",
            type="rect",
            x=0.0,
            y=0.0,
            width=float(width),
            height=float(height),
            fill=_artboard_background(tree),
        ),
    )
    for child in tree.children:
        _append_node_layers(
            child,
            nodes=nodes,
            project_dir=project_dir,
            origin_x=origin_x,
            origin_y=origin_y,
        )
    return PreviewScene(
        width=width,
        height=height,
        background=_artboard_background(tree),
        nodes=nodes,
    )
