"""Component deduplication helpers."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode


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
