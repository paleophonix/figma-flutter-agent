"""Component deduplication helpers."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_DECORATIVE_VECTOR_MAX_WIDTH_PX = 300.0
_BACKGROUND_CONTAINER_MIN_SCREEN_FRACTION = 0.5


@dataclass
class DedupResult:
    """Reusable widget candidates discovered in the design tree."""

    component_refs: dict[str, str] = field(default_factory=dict)
    instance_count: dict[str, int] = field(default_factory=dict)


def collect_component_instances(root: dict[str, Any]) -> DedupResult:
    """Collect component instance references from a Figma subtree.

    Args:
        root: Figma node dictionary.

    Returns:
        Mapping of instance node ids to component ids and usage counts.
    """
    result = DedupResult()

    def walk(node: dict[str, Any]) -> None:
        if node.get("visible") is False:
            return
        if node.get("type") == "INSTANCE":
            component_id = node.get("componentId")
            if component_id:
                result.component_refs[node["id"]] = component_id
                result.instance_count[component_id] = result.instance_count.get(component_id, 0) + 1
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return result


def _node_signature_payload(node: CleanDesignTreeNode, *, include_text: bool) -> dict[str, Any]:
    """Build a JSON-serializable structural signature payload for a node."""
    payload: dict[str, Any] = {
        "type": node.type.value,
        "padding": node.padding.model_dump(),
        "spacing": node.spacing,
        "sizing": node.sizing.model_dump(by_alias=True),
        "alignment": node.alignment.model_dump(),
        "style": node.style.model_dump(by_alias=True),
        "children": [
            _node_signature_payload(child, include_text=include_text) for child in node.children
        ],
    }
    if include_text:
        payload["text"] = node.text
    return payload


def structural_signature(node: CleanDesignTreeNode) -> str:
    """Return a stable hash for a clean-tree subtree including text content."""
    payload = json.dumps(
        _node_signature_payload(node, include_text=True),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cluster_structure_signature(node: CleanDesignTreeNode) -> str:
    """Return a stable hash for deduplication (layout/spacing only, not text)."""
    payload = json.dumps(
        _node_signature_payload(node, include_text=False),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def assign_structural_clusters(
    root: CleanDesignTreeNode,
    *,
    min_count: int = 2,
) -> dict[str, int]:
    """Assign ``cluster_id`` to structurally identical subtrees.

    Args:
        root: Clean design tree root node.
        min_count: Minimum repeated occurrences required to form a cluster.

    Returns:
        Mapping of cluster id to occurrence count.
    """
    by_signature: dict[str, list[str]] = defaultdict(list)

    def collect(node: CleanDesignTreeNode) -> None:
        if node.children:
            by_signature[cluster_structure_signature(node)].append(node.id)
        for child in node.children:
            collect(child)

    collect(root)

    id_to_cluster: dict[str, str] = {}
    summary: dict[str, int] = {}
    cluster_index = 0
    for node_ids in by_signature.values():
        if len(node_ids) < min_count:
            continue
        cluster_id = f"cluster_{cluster_index}"
        cluster_index += 1
        summary[cluster_id] = len(node_ids)
        for node_id in node_ids:
            id_to_cluster[node_id] = cluster_id

    def apply(node: CleanDesignTreeNode) -> None:
        cluster_id = id_to_cluster.get(node.id)
        if cluster_id is not None:
            node.cluster_id = cluster_id
        for child in node.children:
            apply(child)

    apply(root)
    return summary


def component_cluster_id(component_id: str) -> str:
    """Return a stable cluster id for repeated Figma component instances."""
    return f"component_{component_id.replace(':', '_')}"


def assign_component_clusters(
    root: CleanDesignTreeNode,
    dedup: DedupResult,
    *,
    min_count: int = 2,
) -> dict[str, int]:
    """Assign ``cluster_id`` for repeated published component instances.

    Component-backed clusters take precedence over structural clusters on the same node
    so all instances of a Figma component share one extracted widget.

    Args:
        root: Clean design tree root node.
        dedup: Component instance references collected from the raw Figma tree.
        min_count: Minimum instance count required to form a component cluster.

    Returns:
        Mapping of component cluster id to occurrence count.
    """
    summary: dict[str, int] = {}
    for component_id, count in dedup.instance_count.items():
        if count < min_count:
            continue
        summary[component_cluster_id(component_id)] = count

    def walk(node: CleanDesignTreeNode) -> None:
        component_id = dedup.component_refs.get(node.id)
        if component_id and dedup.instance_count.get(component_id, 0) >= min_count:
            node.cluster_id = component_cluster_id(component_id)
        for child in node.children:
            walk(child)

    walk(root)
    return summary


def prune_top_level_cluster_duplicates(root: CleanDesignTreeNode) -> None:
    """Remove later root-level siblings that repeat an already-seen ``cluster_id``.

    Args:
        root: Screen root node (mutated in place).
    """
    if root.type in {NodeType.TABS, NodeType.CAROUSEL}:
        return

    seen_clusters: set[str] = set()
    kept: list[CleanDesignTreeNode] = []
    for child in root.children:
        cluster_id = child.cluster_id
        if cluster_id:
            if cluster_id in seen_clusters:
                continue
            seen_clusters.add(cluster_id)
        kept.append(child)
    root.children = kept


def prune_extracted_subtree_nodes(
    root: CleanDesignTreeNode,
    extracted_node_ids: frozenset[str],
) -> None:
    """Drop nodes already rendered as deterministic subtree widgets from the layout tree.

    Args:
        root: Clean design tree root (mutated in place).
        extracted_node_ids: Figma node ids owned by ``collect_subtree_widget_specs``.
    """
    if not extracted_node_ids:
        return

    def walk(node: CleanDesignTreeNode) -> None:
        node.children = [child for child in node.children if child.id not in extracted_node_ids]
        for child in node.children:
            walk(child)

    walk(root)


def _node_layout_width_px(node: CleanDesignTreeNode) -> float | None:
    width = node.sizing.width
    if width is not None:
        return float(width)
    if node.stack_placement is not None and node.stack_placement.width is not None:
        return float(node.stack_placement.width)
    return None


def _screen_canvas_size(root: CleanDesignTreeNode) -> tuple[float, float]:
    width = root.sizing.width
    height = root.sizing.height
    if width is None or height is None:
        for child in root.children:
            placement = child.stack_placement
            if placement is None:
                continue
            if width is None and placement.width is not None:
                width = placement.width
            if height is None and placement.height is not None:
                height = placement.height
    return float(width or 414.0), float(height or 896.0)


def _is_large_background_container(
    node: CleanDesignTreeNode,
    *,
    canvas_width: float,
    canvas_height: float,
) -> bool:
    name_lower = node.name.lower()
    if "background" not in name_lower and "group" not in name_lower:
        return False
    width = _node_layout_width_px(node)
    height = node.sizing.height
    if height is None and node.stack_placement is not None:
        height = node.stack_placement.height
    if width is None or height is None:
        return False
    return (
        width >= canvas_width * _BACKGROUND_CONTAINER_MIN_SCREEN_FRACTION
        and height >= canvas_height * _BACKGROUND_CONTAINER_MIN_SCREEN_FRACTION
    )


def _node_within_container(node: CleanDesignTreeNode, container: CleanDesignTreeNode) -> bool:
    placement = node.stack_placement
    bounds = container.stack_placement
    if placement is None or bounds is None:
        return False
    if placement.left is None or placement.top is None:
        return False
    left = bounds.left or 0.0
    top = bounds.top or 0.0
    width = bounds.width
    height = bounds.height
    if width is None or height is None:
        return False
    node_width = placement.width or 0.0
    node_height = placement.height or 0.0
    center_x = placement.left + node_width / 2.0
    center_y = placement.top + node_height / 2.0
    return left <= center_x <= left + width and top <= center_y <= top + height


def _protected_by_large_background_container(
    node: CleanDesignTreeNode,
    root: CleanDesignTreeNode,
) -> bool:
    canvas_width, canvas_height = _screen_canvas_size(root)
    for child in root.children:
        if child.type not in {NodeType.STACK, NodeType.CONTAINER, NodeType.COLUMN, NodeType.ROW}:
            continue
        if not _is_large_background_container(
            child,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        ):
            continue
        if _node_within_container(node, child):
            return True
    return False


def is_decorative_absolute_vector(
    node: CleanDesignTreeNode,
    *,
    root: CleanDesignTreeNode | None = None,
) -> bool:
    """True for ambient Figma ``Vector`` blobs that should not become layout widgets."""
    if root is not None and _protected_by_large_background_container(node, root):
        return False
    if node.layout_positioning != "ABSOLUTE":
        return False
    if "Vector" not in node.name:
        return False
    width = _node_layout_width_px(node)
    if width is None or width >= _DECORATIVE_VECTOR_MAX_WIDTH_PX:
        return False
    return node.type == NodeType.VECTOR


def prune_decorative_absolute_vectors(root: CleanDesignTreeNode) -> int:
    """Drop top-level absolute ``Vector`` dust (e.g. soft background circles).

    Only direct children of the screen root are removed so button icons and chrome
    vectors nested in stacks/buttons are preserved.

    Returns:
        Count of removed nodes.
    """
    removed = 0
    kept: list[CleanDesignTreeNode] = []
    for child in root.children:
        if is_decorative_absolute_vector(child, root=root):
            removed += 1
            continue
        kept.append(child)
    root.children = kept
    return removed


def prune_generation_layout_tree(
    root: CleanDesignTreeNode,
    *,
    extracted_subtree_node_ids: frozenset[str] = frozenset(),
) -> None:
    """True subtree pruning for the codegen pool (LLM, layout, anchors).

    Order: remove extracted subtree roots, erase top-level cluster duplicates, then
    clear nested duplicate cluster children for payload compaction.

    Args:
        root: Clean design tree root (mutated in place).
        extracted_subtree_node_ids: Subtree widget representative node ids to remove.
    """
    prune_extracted_subtree_nodes(root, extracted_subtree_node_ids)
    prune_top_level_cluster_duplicates(root)
    prune_duplicated_cluster_subtrees(root)


def _cluster_instance_is_backward(
    node: CleanDesignTreeNode,
    *,
    parent_width: float | None,
) -> bool:
    """Infer rewind vs forward skip from horizontal placement within the parent row."""
    from figma_flutter_agent.parser.interaction import skip_control_left_side_of_parent

    return skip_control_left_side_of_parent(node, parent_width=parent_width)


def prune_duplicated_cluster_subtrees(root: CleanDesignTreeNode) -> None:
    """Clear ``children`` on repeated ``cluster_id`` instances (first instance is canonical).

    Args:
        root: Clean design tree root (mutated in place).
    """
    seen_clusters: set[str] = set()
    cluster_assets: dict[str, tuple[str | None, str | None]] = {}

    def walk(node: CleanDesignTreeNode, parent: CleanDesignTreeNode | None) -> None:
        cluster_id = node.cluster_id
        parent_width = parent.sizing.width if parent is not None else None
        if cluster_id and cluster_id in seen_clusters:
            from figma_flutter_agent.generator.cluster_variants import primary_vector_asset

            asset = primary_vector_asset(node) or node.vector_asset_key
            if asset is None:
                forward, backward = cluster_assets.get(cluster_id, (None, None))
                asset = (
                    backward
                    if _cluster_instance_is_backward(node, parent_width=parent_width)
                    else forward
                )
            if asset is not None:
                node.vector_asset_key = asset
            node.children = []
            return
        if cluster_id:
            from figma_flutter_agent.generator.cluster_variants import primary_vector_asset

            asset = primary_vector_asset(node)
            if asset is not None:
                forward, backward = cluster_assets.get(cluster_id, (None, None))
                if _cluster_instance_is_backward(node, parent_width=parent_width):
                    backward = asset
                else:
                    forward = asset
                cluster_assets[cluster_id] = (forward, backward)
            seen_clusters.add(cluster_id)
        for child in node.children:
            walk(child, node)

    walk(root, None)


def merge_cluster_summaries(*summaries: dict[str, int]) -> dict[str, int]:
    """Merge cluster summary maps (structural + component-backed)."""
    merged: dict[str, int] = {}
    for summary in summaries:
        merged.update(summary)
    return merged


def build_widget_extraction_hints(
    dedup: DedupResult,
    cluster_summary: dict[str, int],
) -> list[str]:
    """Build LLM hints for reusable widget extraction.

    Args:
        dedup: Figma component instance deduplication result.
        cluster_summary: Structural cluster id to occurrence count mapping.

    Returns:
        Human-readable extraction hints for the LLM prompt payload.
    """
    hints: list[str] = []
    for component_id, count in sorted(dedup.instance_count.items()):
        if count >= 2:
            cluster = component_cluster_id(component_id)
            hints.append(
                f"Figma component '{component_id}' appears {count} times "
                f"(cluster '{cluster}'); extract a reusable widget."
            )
    for cluster_id, count in sorted(cluster_summary.items()):
        hints.append(
            f"Structural cluster '{cluster_id}' appears {count} times; extract a shared widget."
        )
    return hints
