"""Collect real cluster call-sites from clean trees (Program 04 P0-3)."""

from __future__ import annotations

from collections import defaultdict

from figma_flutter_agent.generator.extraction.definition_key import DefinitionKey
from figma_flutter_agent.generator.variant_topology import compare_variant_topology
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.parser.tree_walk import walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode


def _key_for_spec(
    spec: ClusterWidgetSpec,
    *,
    topology_by_cluster: dict[str, str],
) -> DefinitionKey:
    variant = topology_by_cluster.get(spec.cluster_id, "default")
    return DefinitionKey.from_spec(spec, topology_variant=variant)


def _resolve_spec_for_node(
    node: CleanDesignTreeNode,
    candidates: list[ClusterWidgetSpec],
) -> ClusterWidgetSpec:
    """Pick the spec variant when multiple definitions share a cluster id."""
    if len(candidates) == 1:
        return candidates[0]
    for spec in candidates:
        if spec.representative is None:
            continue
        if not compare_variant_topology(spec.representative, node).should_split:
            return spec
    return candidates[0]


def collect_cluster_callsites(
    specs: list[ClusterWidgetSpec],
    clean_trees: list[CleanDesignTreeNode],
    *,
    topology_by_cluster: dict[str, str] | None = None,
) -> dict[str, DefinitionKey]:
    """Map concrete usage node ids to definition keys.

    Scans clean trees for nodes carrying a known ``cluster_id`` and includes
    explicit ``shape_members`` from extraction specs.

    Args:
        specs: Cluster widget extraction specs.
        clean_trees: Screen clean trees containing delegate instances.
        topology_by_cluster: Optional topology variant label per cluster id.

    Returns:
        ``callsite_node_id`` → ``DefinitionKey`` (many call-sites may share one key).
    """
    topo = topology_by_cluster or {}
    specs_by_cluster: dict[str, list[ClusterWidgetSpec]] = defaultdict(list)
    for spec in specs:
        specs_by_cluster[spec.cluster_id].append(spec)
    callsites: dict[str, DefinitionKey] = {}

    for spec in specs:
        key = _key_for_spec(spec, topology_by_cluster=topo)
        for member in spec.shape_members:
            callsites[member.id] = key

    def visitor(node: CleanDesignTreeNode) -> None:
        cluster_id = node.cluster_id
        if not cluster_id:
            return
        candidates = specs_by_cluster.get(cluster_id)
        if not candidates:
            return
        spec = _resolve_spec_for_node(node, candidates)
        callsites[node.id] = _key_for_spec(spec, topology_by_cluster=topo)

    for tree in clean_trees:
        walk_clean_tree(tree, visitor, phase="bijection_callsite_collect")

    for spec in specs:
        if spec.representative is not None:
            walk_clean_tree(
                spec.representative,
                visitor,
                phase="bijection_callsite_collect_rep",
            )

    return callsites
