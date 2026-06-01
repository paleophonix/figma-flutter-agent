"""Collapse decorative vector-heavy subtrees into single SVG render boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from figma_flutter_agent.parser.interaction import (
    looks_like_media_controls_stack,
    looks_like_password_field_stack,
    looks_like_play_pause_control_stack,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import AssetManifest, CleanDesignTreeNode, NodeType

_MIN_CHILD_COUNT = 6
_MIN_VECTOR_COUNT = 4
_MIN_BOUNDARY_AREA = 8_000.0
_MAX_COMPACT_BOUNDARY_WIDTH = 64.0
_MAX_COMPACT_BOUNDARY_HEIGHT = 64.0
_MAX_SIGNIFICANT_TEXT_LEN = 32

_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
        NodeType.CAROUSEL,
    }
)
_VISUAL_LEAF_TYPES = frozenset({NodeType.VECTOR, NodeType.IMAGE})
_LAYOUT_CONTAINER_TYPES = frozenset(
    {NodeType.STACK, NodeType.CONTAINER, NodeType.COLUMN, NodeType.ROW}
)


@dataclass
class RenderBoundaryCollapseResult:
    """Outcome of collapsing render boundaries in a clean tree."""

    collapsed_count: int = 0
    flattened_node_ids: frozenset[str] = field(default_factory=frozenset)
    boundary_node_ids: frozenset[str] = field(default_factory=frozenset)


def render_boundary_asset_path(node_id: str) -> str:
    """Relative Flutter asset path reserved for a render-boundary SVG export."""
    safe_id = node_id.replace(":", "_")
    return f"assets/illustrations/render_boundary_{safe_id}.svg"


def discover_asset_path_for_node(project_dir: Path, node_id: str) -> str | None:
    """Find an on-disk SVG/PNG export for a Figma node id (any filename suffix)."""
    suffix = node_id.replace(":", "_")
    for folder in ("icons", "illustrations", "images"):
        asset_dir = project_dir / "assets" / folder
        if not asset_dir.is_dir():
            continue
        for pattern in (f"*_{suffix}.svg", f"*_{suffix}.png", f"render_boundary_{suffix}.svg"):
            matches = sorted(asset_dir.glob(pattern))
            if matches:
                return f"assets/{folder}/{matches[0].name}"
    return None


def resolve_render_boundary_asset_keys(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    manifest: AssetManifest | None = None,
) -> list[str]:
    """Map render-boundary nodes to existing exports; return ids still missing on disk."""
    manifest_paths: dict[str, str] = {}
    if manifest is not None:
        for entry in manifest.entries:
            manifest_paths.setdefault(entry.node_id, entry.asset_path)

    unresolved: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if not node.render_boundary:
            for child in node.children:
                walk(child)
            return
        candidates: list[str] = []
        manifest_path = manifest_paths.get(node.id)
        if manifest_path:
            candidates.append(manifest_path)
        reserved = render_boundary_asset_path(node.id)
        if reserved not in candidates:
            candidates.append(reserved)
        discovered = discover_asset_path_for_node(project_dir, node.id)
        if discovered and discovered not in candidates:
            candidates.append(discovered)
        for candidate in candidates:
            if (project_dir / Path(candidate)).is_file():
                node.vector_asset_key = candidate.replace("\\", "/")
                break
        else:
            unresolved.append(node.id)
        for child in node.children:
            walk(child)

    walk(tree)
    return unresolved


def collect_render_boundary_asset_plan(
    root: CleanDesignTreeNode,
) -> tuple[frozenset[str], frozenset[str]]:
    """Return boundary export ids and flattened descendant ids excluded from per-vector export."""
    export_ids: set[str] = set()
    exclude_ids: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.render_boundary:
            export_ids.add(node.id)
            for flattened_id in node.flatten_figma_node_ids or ():
                exclude_ids.add(flattened_id)
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(export_ids), frozenset(exclude_ids)


def _node_area(node: CleanDesignTreeNode) -> float:
    placement = node.stack_placement
    width = (placement.width if placement is not None else None) or node.sizing.width
    height = (placement.height if placement is not None else None) or node.sizing.height
    if width is None or height is None:
        return 0.0
    return float(width) * float(height)


def _is_compact_boundary(node: CleanDesignTreeNode) -> bool:
    placement = node.stack_placement
    width = (placement.width if placement is not None else None) or node.sizing.width
    height = (placement.height if placement is not None else None) or node.sizing.height
    if width is None or height is None:
        return False
    return (
        float(width) <= _MAX_COMPACT_BOUNDARY_WIDTH
        and float(height) <= _MAX_COMPACT_BOUNDARY_HEIGHT
    )


def _count_vectors(node: CleanDesignTreeNode) -> int:
    total = 0
    if node.type in _VISUAL_LEAF_TYPES:
        total += 1
    if node.vector_asset_key or node.image_asset_key:
        total += 1
    for child in node.children:
        total += _count_vectors(child)
    return total


def _count_decorative_leaves(node: CleanDesignTreeNode) -> int:
    if node.type in _VISUAL_LEAF_TYPES:
        return 1
    if node.vector_asset_key or node.image_asset_key:
        return 1
    if not node.children:
        if node.type == NodeType.CONTAINER and (
            node.style.background_color
            or node.style.border_color
            or node.style.gradient is not None
        ):
            return 1
        return 0
    return sum(_count_decorative_leaves(child) for child in node.children)


def _count_children(node: CleanDesignTreeNode) -> int:
    total = len(node.children)
    for child in node.children:
        total += _count_children(child)
    return total


def _collect_descendant_ids(node: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []
    for child in node.children:
        ids.append(child.id)
        ids.extend(_collect_descendant_ids(child))
    return ids


def _has_interactive_semantics(node: CleanDesignTreeNode) -> bool:
    if node.type in _INTERACTIVE_TYPES:
        return True
    if node.extracted_widget_ref:
        return True
    if node.type == NodeType.STACK and stack_interaction_kind(node) is not None:
        return True
    if looks_like_password_field_stack(node):
        return True
    if looks_like_media_controls_stack(node):
        return True
    if looks_like_play_pause_control_stack(node):
        return True
    return False


def _has_significant_copy(node: CleanDesignTreeNode) -> bool:
    if node.type == NodeType.TEXT and node.text:
        return len(node.text.strip()) > _MAX_SIGNIFICANT_TEXT_LEN
    return any(_has_significant_copy(child) for child in node.children)


def _is_illustration_card(node: CleanDesignTreeNode) -> bool:
    if _node_area(node) < 30_000.0:
        return False
    has_copy = any(child.type == NodeType.TEXT and child.text for child in node.children) or any(
        _is_illustration_card(child) for child in node.children
    )
    if not has_copy:
        return False
    return _count_decorative_leaves(node) >= 2


def _is_visual_only_subtree(node: CleanDesignTreeNode) -> bool:
    if _has_interactive_semantics(node):
        return False
    if node.type in _VISUAL_LEAF_TYPES:
        return True
    if node.type == NodeType.TEXT:
        return True
    if node.type == NodeType.BUTTON:
        return True
    if node.type not in _LAYOUT_CONTAINER_TYPES:
        return False
    if not node.children:
        return True
    return all(_is_visual_only_subtree(child) for child in node.children)


def _is_absolute_graphic_container(node: CleanDesignTreeNode) -> bool:
    if node.type not in {NodeType.STACK, NodeType.CONTAINER}:
        return False
    if node.stack_placement is None and node.layout_positioning != "ABSOLUTE":
        return False
    return True


def _boundary_denied(
    node: CleanDesignTreeNode,
    *,
    parent: CleanDesignTreeNode | None,
    screen_root: CleanDesignTreeNode,
) -> bool:
    if node.render_boundary:
        return True
    if (
        parent is screen_root
        and _has_significant_copy(node)
        and not _is_illustration_card(node)
    ):
        return True
    if _has_interactive_semantics(node) and not _is_illustration_card(node):
        return True
    return False


def _should_collapse_boundary(
    node: CleanDesignTreeNode,
    *,
    parent: CleanDesignTreeNode | None,
    screen_root: CleanDesignTreeNode,
) -> bool:
    if not _is_absolute_graphic_container(node):
        return False
    if _boundary_denied(node, parent=parent, screen_root=screen_root):
        return False
    if not _is_visual_only_subtree(node):
        return False
    if _is_compact_boundary(node):
        return False
    area = _node_area(node)
    min_child_count = _MIN_CHILD_COUNT
    min_visual_mass = _MIN_VECTOR_COUNT
    if area >= 150_000.0:
        min_child_count = 2
        min_visual_mass = 2
    decorative_leaves = _count_decorative_leaves(node)
    vector_count = _count_vectors(node)
    visual_mass = max(decorative_leaves, vector_count)
    if visual_mass < min_visual_mass:
        return False
    child_count = _count_children(node)
    if child_count < min_child_count:
        return False
    if area < _MIN_BOUNDARY_AREA and visual_mass < min_child_count:
        return False
    return True


def _pin_render_boundary_placement(
    node: CleanDesignTreeNode,
    *,
    parent_height: float | None,
) -> None:
    placement = node.stack_placement
    if placement is None:
        return
    height = placement.height or node.sizing.height
    if height is None or height <= 0:
        return
    top = placement.top
    if (top is None or top <= 0.0) and parent_height is not None and placement.bottom > 0:
        top = float(parent_height) - float(placement.bottom) - float(height)
    if top is None or top < 0:
        top = node.offset_y
    rounded_top = round_geometry(top)
    node.stack_placement = placement.model_copy(
        update={
            "vertical": "TOP",
            "top": rounded_top if rounded_top is not None else top,
            "bottom": 0.0,
        },
    )


def _collapse_node(
    node: CleanDesignTreeNode,
    result: RenderBoundaryCollapseResult,
    *,
    parent_height: float | None,
) -> None:
    flattened = _collect_descendant_ids(node)
    node.children = []
    node.render_boundary = True
    node.flatten_figma_node_ids = flattened
    node.vector_asset_key = render_boundary_asset_path(node.id)
    node.vector_svg_has_filter = False
    _pin_render_boundary_placement(node, parent_height=parent_height)
    result.collapsed_count += 1
    result.boundary_node_ids = frozenset(set(result.boundary_node_ids) | {node.id})
    result.flattened_node_ids = frozenset(set(result.flattened_node_ids) | set(flattened))


def _walk_and_collapse(
    node: CleanDesignTreeNode,
    result: RenderBoundaryCollapseResult,
    *,
    parent: CleanDesignTreeNode | None,
    screen_root: CleanDesignTreeNode,
    parent_height: float | None,
) -> None:
    if _should_collapse_boundary(node, parent=parent, screen_root=screen_root):
        _collapse_node(node, result, parent_height=parent_height)
        return
    child_parent_height = node.sizing.height or parent_height
    for child in list(node.children):
        _walk_and_collapse(
            child,
            result,
            parent=node,
            screen_root=screen_root,
            parent_height=child_parent_height,
        )


def collapse_render_boundaries(root: CleanDesignTreeNode) -> RenderBoundaryCollapseResult:
    """Collapse decorative vector-heavy subtrees into single SVG boundaries."""
    result = RenderBoundaryCollapseResult()
    screen_height = root.sizing.height
    for child in list(root.children):
        _walk_and_collapse(
            child,
            result,
            parent=root,
            screen_root=root,
            parent_height=screen_height,
        )
    if result.collapsed_count:
        logger.info(
            "Render boundaries collapsed={} flattened_nodes={} boundaries={}",
            result.collapsed_count,
            len(result.flattened_node_ids),
            len(result.boundary_node_ids),
        )
    return result
