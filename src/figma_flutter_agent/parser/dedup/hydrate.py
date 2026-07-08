"""Hydrate cluster-pruned component instances from inline templates."""

from __future__ import annotations

from figma_flutter_agent.parser.tree_walk import walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _variant_key_suffix(node: CleanDesignTreeNode) -> str:
    """Serialize component variant props for stable hydration lookup."""
    if node.variant is None:
        return ""
    props = node.variant.variant_properties or {}
    if not props:
        return ""
    prop_key = tuple(sorted(props.items()))
    return f":{prop_key!r}"


def _component_instance_lookup_keys(node: CleanDesignTreeNode) -> list[str]:
    """Return hydration lookup keys from most specific to fallback buckets."""
    keys: list[str] = []
    if node.cluster_id:
        if node.component_ref:
            keys.append(
                f"cluster:{node.cluster_id}:comp:{node.component_ref}{_variant_key_suffix(node)}"
            )
        keys.append(f"cluster:{node.cluster_id}")
        if node.children:
            from figma_flutter_agent.parser.dedup.signatures import cluster_structure_signature

            keys.append(f"cluster:{node.cluster_id}:{cluster_structure_signature(node)}")
        else:
            keys.append(f"cluster:{node.cluster_id}:leaf")
    if node.component_ref and node.variant is not None:
        props = node.variant.variant_properties or {}
        prop_key = tuple(sorted(props.items()))
        keys.append(f"comp:{node.component_ref}:{prop_key}")
    elif node.component_ref:
        keys.append(f"comp:{node.component_ref}")
    seen: set[str] = set()
    ordered: list[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def _component_instance_key(node: CleanDesignTreeNode) -> str | None:
    """Return the primary stable lookup key for duplicated component instances."""
    keys = _component_instance_lookup_keys(node)
    return keys[0] if keys else None


def _inline_content_score(node: CleanDesignTreeNode) -> int:
    """Prefer templates that still carry renderable inline children."""
    if not node.children:
        return 0
    score = len(node.children) * 10

    def walk(current: CleanDesignTreeNode) -> None:
        nonlocal score
        if current.text and current.text.strip():
            score += 5
        for child in current.children:
            walk(child)

    for child in node.children:
        walk(child)
    return score


def _hydrate_component_instance_from_template(
    target: CleanDesignTreeNode,
    template: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Copy inline children from a rich template onto a pruned duplicate instance."""
    from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
    from figma_flutter_agent.parser.layout.reconcilers_grid_hydrate import (
        _build_product_card_hydration_id_map,
        _clear_cluster_ids_subtree,
        _remap_subtree_node_ids,
        _subtree_paths,
    )

    if not template.children:
        return target
    id_map = _build_product_card_hydration_id_map(
        template,
        target,
        reserved_ids={target.id},
    )
    template_paths = _subtree_paths(template)
    if any(template_paths[path] not in id_map for path in template_paths):
        return target
    hydrated = _clear_cluster_ids_subtree(deep_copy_clean_tree(template))
    hydrated = _remap_subtree_node_ids(
        hydrated,
        id_map,
        template_root=template.id,
        target_root=target.id,
    )
    updates: dict[str, object] = {
        "children": hydrated.children,
        "flatten_figma_node_ids": None,
    }
    if target.type == NodeType.CARD:
        updates["vector_asset_key"] = None
        updates["image_asset_key"] = None
    return target.model_copy(update=updates)


def _should_hydrate_pruned_instance(node: CleanDesignTreeNode) -> bool:
    """Return True when a pruned duplicate should regain inline children."""
    if node.children:
        return False
    if node.type in {NodeType.VECTOR, NodeType.IMAGE}:
        return False
    if node.type == NodeType.CARD and node.flatten_figma_node_ids and node.cluster_id:
        return True
    if node.vector_asset_key or node.image_asset_key:
        from figma_flutter_agent.generator.layout.widgets import _sizing_like_skip_control

        if _sizing_like_skip_control(node):
            return False
    if node.cluster_id or node.component_ref:
        return True
    if not node.flatten_figma_node_ids:
        return False
    if node.vector_asset_key or node.image_asset_key:
        return False
    return False


def hydrate_pruned_cluster_instances(root: CleanDesignTreeNode) -> None:
    """Restore inline children on cluster-pruned duplicates from the richest template."""
    templates: dict[str, CleanDesignTreeNode] = {}

    def collect(node: CleanDesignTreeNode) -> None:
        if not node.children:
            return
        for key in _component_instance_lookup_keys(node):
            existing = templates.get(key)
            if existing is None or _inline_content_score(node) > _inline_content_score(existing):
                templates[key] = node

    walk_clean_tree(root, collect, phase="dedup_hydrate_collect")

    def apply_hydration(node: CleanDesignTreeNode) -> None:
        if not _should_hydrate_pruned_instance(node):
            return
        template: CleanDesignTreeNode | None = None
        for key in _component_instance_lookup_keys(node):
            candidate = templates.get(key)
            if candidate is not None and candidate.id != node.id:
                template = candidate
                break
        if template is not None:
            hydrated = _hydrate_component_instance_from_template(node, template)
            node.children = hydrated.children
            node.flatten_figma_node_ids = hydrated.flatten_figma_node_ids
            if node.type == NodeType.CARD:
                node.vector_asset_key = hydrated.vector_asset_key
                node.image_asset_key = hydrated.image_asset_key

    walk_clean_tree(root, apply_hydration, phase="dedup_hydrate_apply")
    from figma_flutter_agent.generator.ir.tree import validate_unique_node_ids

    validate_unique_node_ids(root)
