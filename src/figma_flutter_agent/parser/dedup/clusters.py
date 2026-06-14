"""Cluster assignment for repeated clean-tree subtrees."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from figma_flutter_agent.parser.dedup.instances import DedupResult
from figma_flutter_agent.parser.dedup.signatures import (
    cluster_structure_signature,
    descendant_text_fingerprint,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def assign_structural_clusters(
    root: CleanDesignTreeNode,
    *,
    min_count: int = 2,
) -> dict[str, int]:
    """Assign ``cluster_id`` to structurally identical subtrees."""
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


def component_cluster_id(
    component_id: str,
    *,
    text_fingerprint: tuple[str, ...] = (),
) -> str:
    """Return a stable cluster id for repeated Figma component instances."""
    base = f"component_{component_id.replace(':', '_')}"
    if not text_fingerprint:
        return base
    digest = hashlib.sha256(repr(text_fingerprint).encode("utf-8")).hexdigest()[:8]
    return f"{base}_{digest}"


def assign_component_clusters(
    root: CleanDesignTreeNode,
    dedup: DedupResult,
    *,
    min_count: int = 2,
) -> dict[str, int]:
    """Assign ``cluster_id`` for repeated published component instances."""
    summary: dict[str, int] = {}
    cluster_counts: dict[str, int] = defaultdict(int)

    def walk(node: CleanDesignTreeNode) -> None:
        component_id = dedup.component_refs.get(node.id)
        if component_id and dedup.instance_count.get(component_id, 0) >= min_count:
            fingerprint = descendant_text_fingerprint(node)
            cluster_id = component_cluster_id(component_id, text_fingerprint=fingerprint)
            node.cluster_id = cluster_id
            cluster_counts[cluster_id] += 1
        for child in node.children:
            walk(child)

    walk(root)
    for cluster_id, count in cluster_counts.items():
        if count >= min_count:
            summary[cluster_id] = count
    return summary


def merge_cluster_summaries(*summaries: dict[str, int]) -> dict[str, int]:
    """Merge cluster summary maps (structural + component-backed)."""
    merged: dict[str, int] = {}
    for summary in summaries:
        merged.update(summary)
    return merged
