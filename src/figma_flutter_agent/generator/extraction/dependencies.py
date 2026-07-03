"""Deterministic cluster definition dependency derivation (04-P0-3a)."""

from __future__ import annotations

from figma_flutter_agent.generator.extraction.definition_key import (
    DefinitionKey,
    topology_variant_for_spec,
)
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.parser.tree_walk import walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode


def derive_definition_dependencies(
    representative: CleanDesignTreeNode,
    *,
    self_key: DefinitionKey,
    callsite_to_definition: dict[str, DefinitionKey],
) -> frozenset[DefinitionKey]:
    """Collect nested delegate call-sites inside a definition body.

    Edges are keyed by actual nested node ids via ``callsite_to_definition`` —
    no intermediate ``cluster_id`` index (avoids topology last-wins).

    Args:
        representative: Definition body root subtree.
        self_key: Definition key for this body (root id skipped as trivial self).
        callsite_to_definition: Global call-site → definition map.

    Returns:
        Frozen set of referenced definition keys (self-edges preserved).
    """
    deps: set[DefinitionKey] = set()
    root_id = self_key.representative_node_id

    def visitor(node: CleanDesignTreeNode) -> None:
        if node.id == root_id:
            return
        dep_key = callsite_to_definition.get(node.id)
        if dep_key is not None:
            deps.add(dep_key)

    walk_clean_tree(representative, visitor, phase="bijection_dependencies")
    return frozenset(deps)


def build_definition_dependency_map(
    specs: list[ClusterWidgetSpec],
    *,
    callsite_to_definition: dict[str, DefinitionKey],
) -> dict[DefinitionKey, frozenset[DefinitionKey]]:
    """Build ``dependencies`` map for a full extraction plan."""
    result: dict[DefinitionKey, frozenset[DefinitionKey]] = {}
    for spec in specs:
        key = DefinitionKey.from_spec(
            spec,
            topology_variant=topology_variant_for_spec(spec),
        )
        if spec.representative is None:
            result[key] = frozenset()
            continue
        result[key] = derive_definition_dependencies(
            spec.representative,
            self_key=key,
            callsite_to_definition=callsite_to_definition,
        )
    return result


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
