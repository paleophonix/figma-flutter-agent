"""Cluster form-field restore and relabel passes after dedup pruning."""

from __future__ import annotations

from collections import defaultdict

from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_MAX_COMPACT_FORM_FIELD_HEIGHT = 120.0
_GENERIC_FIELD_NAMES = frozenset({"input field", "input", "field", "text field"})
_ORDINAL_FIELD_LABELS = ("Email", "Password")


def _is_compact_form_field_cluster_input(node: CleanDesignTreeNode) -> bool:
    """True for compact clustered ``INPUT`` shells in paired email/password forms."""
    if node.type != NodeType.INPUT:
        return False
    height = node.sizing.height
    if height is None or float(height) > _MAX_COMPACT_FORM_FIELD_HEIGHT:
        return False
    return bool(node.cluster_id)


def is_compact_flex_form_field_host(node: CleanDesignTreeNode) -> bool:
    """True for compact flex ``INPUT`` shells with a title row and nested input area."""
    if not _is_compact_form_field_cluster_input(node):
        return False
    from figma_flutter_agent.parser.interaction.input_fields import (
        input_field_label_node,
        input_surface_node,
    )

    if input_field_label_node(node) is not None or input_surface_node(node) is not None:
        return True
    has_title = any(
        child.type in {NodeType.ROW, NodeType.COLUMN}
        and any(grandchild.type == NodeType.TEXT for grandchild in child.children)
        for child in node.children
    )
    has_nested_input = any(child.type == NodeType.INPUT for child in node.children)
    return has_title and has_nested_input


def cluster_duplicate_keeps_form_field_subtree(node: CleanDesignTreeNode) -> bool:
    """Return True when a duplicate cluster instance must keep its form-field subtree."""
    return is_compact_flex_form_field_host(node)


def _field_label_text(node: CleanDesignTreeNode) -> str:
    from figma_flutter_agent.parser.interaction.input_fields import input_field_label_node

    label = input_field_label_node(node)
    if label is None:
        return (node.accessibility_label or node.name or "").strip().lower()
    return (label.text or label.name or "").strip().lower()


def relabel_duplicate_form_field_cluster_inputs(root: CleanDesignTreeNode) -> None:
    """Assign Email/Password captions when duplicate compact fields share generic copy."""
    by_parent_cluster: dict[tuple[str, str], list[CleanDesignTreeNode]] = defaultdict(list)

    def walk(node: CleanDesignTreeNode, parent_id: str) -> None:
        if (
            node.type == NodeType.INPUT
            and node.cluster_id
            and _is_compact_form_field_cluster_input(node)
        ):
            by_parent_cluster[(parent_id, node.cluster_id)].append(node)
        for child in node.children:
            walk(child, node.id)

    walk(root, "")

    for peers in by_parent_cluster.values():
        if len(peers) < 2:
            continue
        peers.sort(
            key=lambda item: float(item.stack_placement.top or 0)
            if item.stack_placement is not None
            else 0.0
        )
        for index, peer in enumerate(peers):
            if index >= len(_ORDINAL_FIELD_LABELS):
                break
            label_text = _field_label_text(peer)
            if label_text and label_text not in _GENERIC_FIELD_NAMES:
                continue
            from figma_flutter_agent.parser.interaction.input_fields import (
                input_field_label_node,
            )

            label_node = input_field_label_node(peer)
            if label_node is not None:
                label_node.text = _ORDINAL_FIELD_LABELS[index]
            else:
                peer.accessibility_label = _ORDINAL_FIELD_LABELS[index]


def _collect_tree_node_ids(root: CleanDesignTreeNode) -> set[str]:
    collected: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        collected.add(node.id)
        for stub_id in node.flatten_figma_node_ids or []:
            collected.add(stub_id)
        for child in node.children:
            walk(child)

    walk(root)
    return collected


def _remap_subtree_ids(node: CleanDesignTreeNode, taken: set[str]) -> CleanDesignTreeNode:
    copy = deep_copy_clean_tree(node)
    suffix = 0

    def remap(current: CleanDesignTreeNode) -> None:
        nonlocal suffix
        base = current.id
        new_id = base
        while new_id in taken:
            suffix += 1
            new_id = f"{base}@dup{suffix}"
        taken.add(new_id)
        current.id = new_id
        current.flatten_figma_node_ids = []
        for child in current.children:
            remap(child)

    remap(copy)
    return copy


def restore_pruned_cluster_form_field_children(root: CleanDesignTreeNode) -> None:
    """Restore children on pruned duplicate compact form fields with remapped ids."""
    templates: dict[str, CleanDesignTreeNode] = {}
    taken = _collect_tree_node_ids(root)

    def index_templates(node: CleanDesignTreeNode) -> None:
        cluster_id = node.cluster_id
        if cluster_id and _is_compact_form_field_cluster_input(node) and node.children:
            current = templates.get(cluster_id)
            if current is None or len(node.children) > len(current.children):
                templates[cluster_id] = node
        for child in node.children:
            index_templates(child)

    index_templates(root)

    def restore(node: CleanDesignTreeNode) -> None:
        cluster_id = node.cluster_id
        if (
            cluster_id
            and not node.children
            and _is_compact_form_field_cluster_input(node)
            and cluster_id in templates
        ):
            template = templates[cluster_id]
            if template.id != node.id:
                restored = _remap_subtree_ids(template, taken)
                node.children = restored.children
        for child in node.children:
            restore(child)

    restore(root)
    relabel_duplicate_form_field_cluster_inputs(root)
