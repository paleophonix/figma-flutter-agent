"""Large subtree presence injection for screen IR."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.ir.presence.constants import MAX_PRESENCE_SUBTREE_IR_INSERTS
from figma_flutter_agent.generator.ir.presence.tree import clean_parent, find_ir_node, ir_figma_ids
from figma_flutter_agent.generator.ir.tree import index_clean_tree
from figma_flutter_agent.generator.subtree import (
    SubtreeWidgetSpec,
    collect_subtree_widget_specs,
)
from figma_flutter_agent.generator.subtree.placement import _should_insert_missing_subtree
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr, WidgetIrKind, WidgetIrNode


def subtree_root_ids(
    clean_tree: CleanDesignTreeNode,
    *,
    widget_suffix: str = "Widget",
) -> frozenset[str]:
    specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    return frozenset(spec.node_id for spec in specs)


def screen_stack_parent_id(
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
        parent = clean_parent(current_id, tree_by_id)
        if parent is None:
            return screen_ir.root.figma_id
        if parent.id == screen_ir.root.figma_id:
            return screen_ir.root.figma_id
        if parent.stack_placement is not None:
            return parent.id
        current_id = parent.id


def attach_presence_child(
    screen_ir: ScreenIr,
    *,
    spec: SubtreeWidgetSpec,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    """Insert an AUTO IR node for a clean-tree subtree omitted by the LLM."""
    clean = tree_by_id.get(spec.node_id)
    if clean is None:
        return False
    parent_id = screen_stack_parent_id(spec.node_id, screen_ir=screen_ir, tree_by_id=tree_by_id)
    if parent_id is None:
        return False
    parent_ir = find_ir_node(screen_ir.root, parent_id)
    if parent_ir is None:
        return False
    if any(child.figma_id == spec.node_id for child in parent_ir.children):
        return True
    parent_ir.children.append(WidgetIrNode(figma_id=spec.node_id, kind=WidgetIrKind.AUTO))
    logger.debug(
        "Inserted presence IR node for {} (figmaId={}) under parent {}",
        spec.class_name,
        spec.node_id,
        parent_id,
    )
    return True


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
    present = ir_figma_ids(screen_ir.root)
    inserted = 0
    skipped_cap = 0
    for spec in specs:
        if inserted >= MAX_PRESENCE_SUBTREE_IR_INSERTS:
            skipped_cap += 1
            continue
        if not _should_insert_missing_subtree(spec):
            continue
        if spec.node_id in present:
            continue
        if attach_presence_child(screen_ir, spec=spec, tree_by_id=tree_by_id):
            present.add(spec.node_id)
            inserted += 1
    if skipped_cap:
        logger.warning(
            "IR subtree presence capped: inserted {}, skipped {} (max {})",
            inserted,
            skipped_cap,
            MAX_PRESENCE_SUBTREE_IR_INSERTS,
        )
    return screen_ir
