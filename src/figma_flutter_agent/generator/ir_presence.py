"""Ensure large deterministic subtrees appear in screen IR before emission."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.ir_tree import index_clean_tree
from figma_flutter_agent.generator.subtree_widgets import (
    SubtreeWidgetSpec,
    _should_insert_missing_subtree,
    collect_subtree_widget_specs,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr, WidgetIrKind, WidgetIrNode


def _ir_figma_ids(root: WidgetIrNode) -> set[str]:
    ids: set[str] = set()

    def walk(node: WidgetIrNode) -> None:
        ids.add(node.figma_id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _attach_presence_child(
    screen_ir: ScreenIr,
    *,
    spec: SubtreeWidgetSpec,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    """Insert an AUTO IR node for a clean-tree subtree omitted by the LLM."""
    clean = tree_by_id.get(spec.node_id)
    if clean is None:
        return False
    parent_id = _screen_stack_parent_id(spec.node_id, screen_ir=screen_ir, tree_by_id=tree_by_id)
    if parent_id is None:
        return False
    parent_ir = _find_ir_node(screen_ir.root, parent_id)
    if parent_ir is None:
        return False
    if any(child.figma_id == spec.node_id for child in parent_ir.children):
        return True
    parent_ir.children.append(
        WidgetIrNode(
            figma_id=spec.node_id,
            kind=WidgetIrKind.AUTO,
            children=[],
        )
    )
    logger.info(
        "Inserted presence IR node for {} (figmaId={}) under parent {}",
        spec.class_name,
        spec.node_id,
        parent_id,
    )
    return True


def _screen_stack_parent_id(
    node_id: str,
    *,
    screen_ir: ScreenIr,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> str | None:
    """Return the IR parent id that should list ``node_id`` as a direct stack child."""
    node = tree_by_id.get(node_id)
    if node is None:
        return None
    current_id = node_id
    while True:
        parent = _clean_parent(current_id, tree_by_id)
        if parent is None:
            return screen_ir.root.figma_id
        if parent.id == screen_ir.root.figma_id:
            return screen_ir.root.figma_id
        if parent.stack_placement is not None:
            return parent.id
        current_id = parent.id


def _clean_parent(
    node_id: str,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> CleanDesignTreeNode | None:
    for candidate in tree_by_id.values():
        if any(child.id == node_id for child in candidate.children):
            return candidate
    return None


def _find_ir_node(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if root.figma_id == figma_id:
        return root
    for child in root.children:
        found = _find_ir_node(child, figma_id)
        if found is not None:
            return found
    return None


def ensure_presence_subtrees_in_screen_ir(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    widget_suffix: str = "Widget",
) -> ScreenIr:
    """Add AUTO IR nodes for large subtree widgets missing from the LLM screen graph."""
    specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    if not specs:
        return screen_ir
    screen_ir = screen_ir.model_copy(deep=True)
    tree_by_id = index_clean_tree(clean_tree)
    present = _ir_figma_ids(screen_ir.root)
    for spec in specs:
        if not _should_insert_missing_subtree(spec):
            continue
        if spec.node_id in present:
            continue
        if _attach_presence_child(screen_ir, spec=spec, tree_by_id=tree_by_id):
            present.add(spec.node_id)
    return screen_ir
