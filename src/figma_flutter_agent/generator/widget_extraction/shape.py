"""Shape-only cluster indexing for parameterized widget extraction."""

from __future__ import annotations

from collections import defaultdict

from figma_flutter_agent.generator.variant_topology import compare_variant_topology
from figma_flutter_agent.parser.dedup.signatures import shape_structure_signature
from figma_flutter_agent.schemas import CleanDesignTreeNode


def index_shape_clusters(
    root: CleanDesignTreeNode,
    *,
    min_count: int = 2,
) -> tuple[dict[str, int], dict[str, list[CleanDesignTreeNode]]]:
    """Group nodes by shape signature without mutating structural ``cluster_id``."""
    by_signature: dict[str, list[CleanDesignTreeNode]] = defaultdict(list)

    def collect(node: CleanDesignTreeNode) -> None:
        if node.children:
            by_signature[shape_structure_signature(node)].append(node)
        for child in node.children:
            collect(child)

    collect(root)
    summary: dict[str, int] = {}
    members: dict[str, list[CleanDesignTreeNode]] = {}
    cluster_index = 0
    for nodes in by_signature.values():
        if len(nodes) < min_count:
            continue
        groups = _topology_groups(nodes)
        for group in groups:
            if len(group) < min_count:
                continue
            cluster_id = f"shape_{cluster_index}"
            cluster_index += 1
            summary[cluster_id] = len(group)
            members[cluster_id] = group
    return summary, members


def _topology_groups(nodes: list[CleanDesignTreeNode]) -> list[list[CleanDesignTreeNode]]:
    groups: list[list[CleanDesignTreeNode]] = []
    for node in nodes:
        matched = False
        for group in groups:
            if not compare_variant_topology(group[0], node).should_split:
                group.append(node)
                matched = True
                break
        if not matched:
            groups.append([node])
    return groups


def assign_shape_clusters(
    root: CleanDesignTreeNode,
    *,
    min_count: int = 2,
) -> dict[str, int]:
    """Assign ``shape_cluster_id`` on nodes that share shape-only signatures."""
    summary, members = index_shape_clusters(root, min_count=min_count)
    node_to_cluster: dict[str, str] = {}
    for cluster_id, nodes in members.items():
        for node in nodes:
            node_to_cluster[node.id] = cluster_id

    def apply(node: CleanDesignTreeNode) -> None:
        shape_id = node_to_cluster.get(node.id)
        if shape_id is not None:
            node.shape_cluster_id = shape_id
        for child in node.children:
            apply(child)

    apply(root)
    return summary
