"""Deterministic cluster definition dependency derivation (04-P0-3a)."""

from __future__ import annotations

from figma_flutter_agent.generator.extraction.definition_key import DefinitionKey
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.parser.tree_walk import walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode


def derive_definition_dependencies(
    spec: ClusterWidgetSpec,
    *,
    key_by_cluster_id: dict[str, DefinitionKey],
    self_key: DefinitionKey,
) -> frozenset[DefinitionKey]:
    """Collect nested cluster references inside a representative subtree.

    Single deterministic API: nested ``cluster_id`` on descendants (excluding self).

    Args:
        spec: Cluster widget spec whose representative subtree is scanned.
        key_by_cluster_id: Plan keys indexed by ``cluster_id``.
        self_key: Definition key for ``spec`` (excluded from deps).

    Returns:
        Frozen set of dependency definition keys.
    """
    if spec.representative is None:
        return frozenset()
    deps: set[DefinitionKey] = set()

    def visitor(node: CleanDesignTreeNode) -> None:
        nested_id = node.cluster_id
        if not nested_id or nested_id == spec.cluster_id:
            return
        dep_key = key_by_cluster_id.get(nested_id)
        if dep_key is not None and dep_key != self_key:
            deps.add(dep_key)

    walk_clean_tree(spec.representative, visitor, phase="bijection_dependencies")
    return frozenset(deps)


def build_definition_dependency_map(
    specs: list[ClusterWidgetSpec],
    *,
    topology_by_cluster: dict[str, str] | None = None,
) -> dict[DefinitionKey, frozenset[DefinitionKey]]:
    """Build ``dependencies`` map for a full extraction plan."""
    topo = topology_by_cluster or {}
    key_by_cluster_id = {
        spec.cluster_id: DefinitionKey.from_spec(
            spec,
            topology_variant=topo.get(spec.cluster_id, "default"),
        )
        for spec in specs
    }
    return {
        key: derive_definition_dependencies(
            spec,
            key_by_cluster_id=key_by_cluster_id,
            self_key=key,
        )
        for spec in specs
        for key in (key_by_cluster_id[spec.cluster_id],)
    }


def find_dependency_cycles(
    dependencies: dict[DefinitionKey, frozenset[DefinitionKey]],
) -> list[tuple[DefinitionKey, ...]]:
    """Return definition-key cycles in the dependency graph."""
    cycles: list[tuple[DefinitionKey, ...]] = []
    visited: set[DefinitionKey] = set()
    stack: list[DefinitionKey] = []
    on_stack: set[DefinitionKey] = set()

    def dfs(node: DefinitionKey) -> None:
        if node in on_stack:
            start = stack.index(node)
            cycles.append(tuple(stack[start:]) + (node,))
            return
        if node in visited:
            return
        visited.add(node)
        on_stack.add(node)
        stack.append(node)
        for dep in sorted(dependencies.get(node, frozenset()), key=repr):
            dfs(dep)
        stack.pop()
        on_stack.remove(node)

    for key in sorted(dependencies, key=repr):
        dfs(key)
    return cycles
