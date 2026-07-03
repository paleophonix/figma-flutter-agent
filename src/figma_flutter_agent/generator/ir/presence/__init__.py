"""Ensure large deterministic subtrees appear in screen IR before emission."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.presence.constants import (
    MAX_STACK_VISUAL_IR_INSERTS,
    MAX_SYNC_STACK_IR_NODES,
    MIN_STACK_VISUAL_IR_COVERAGE,
    STRUCTURAL_IR_SYNC_TYPES,
)
from figma_flutter_agent.generator.ir.presence.kinds import ir_kind_for_clean_node
from figma_flutter_agent.generator.ir.presence.sanitize import (
    SanitizeSummary,
    sanitize_screen_ir_adaptive_rules,
    sanitize_screen_ir_duplicate_figma_ids,
    sanitize_screen_ir_extracted_refs,
    sanitize_screen_ir_fidelity_authority,
    sanitize_screen_ir_llm_drift,
    sanitize_screen_ir_omit_figma_ids,
    sanitize_screen_ir_phantom_nodes,
    sanitize_screen_ir_state_by_figma_id,
)
from figma_flutter_agent.generator.ir.presence.stack import (
    container_requires_stack_visual_ir,
    ensure_stack_visual_nodes_in_screen_ir,
    should_downgrade_extracted_stack,
    stack_visual_node_requires_ir,
)
from figma_flutter_agent.generator.ir.presence.subtrees import (
    ensure_presence_subtrees_in_screen_ir,
    subtree_root_ids,
)
from figma_flutter_agent.generator.ir.presence.tree import (
    build_clean_parent_map,
    extracted_ir_nodes,
    extracted_reference_valid,
    find_ir_node,
    ir_figma_ids,
    ir_node_by_figma_id,
)
from figma_flutter_agent.generator.ir.tree import index_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


def expand_extracted_widget_names_for_validate(
    extracted_widget_names: frozenset[str],
    *,
    clean_tree: CleanDesignTreeNode | None = None,
    screen_ir: ScreenIr | None = None,
    widget_suffix: str = "Widget",
) -> frozenset[str]:
    """Union LLM extracted names with subtree specs and IR refs for validation."""
    from figma_flutter_agent.generator.subtree import collect_subtree_widget_specs

    expanded = set(extracted_widget_names)
    if clean_tree is not None:
        for spec in collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix):
            expanded.add(spec.class_name)
    if screen_ir is not None:
        for node in extracted_ir_nodes(screen_ir.root):
            ref_name = (node.ref.widget_name if node.ref else "").strip()
            if ref_name:
                expanded.add(ref_name)
    return frozenset(expanded)


def sync_screen_ir_stack_subtree_from_clean_tree(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
    subtree_root_ids: frozenset[str] | None = None,
    widget_suffix: str = "Widget",
) -> ScreenIr:
    """Mirror clean-tree STACK children into screen IR so stack-placed nodes are not dropped."""
    screen_ir = screen_ir.model_copy(deep=True)
    tree_by_id = index_clean_tree(clean_tree)
    if subtree_root_ids is None:
        subtree_root_ids = globals()["subtree_root_ids"](clean_tree, widget_suffix=widget_suffix)
    omit = frozenset(screen_ir.omit_figma_ids)
    root_ir = find_ir_node(screen_ir.root, screen_ir.root.figma_id)
    root_clean = tree_by_id.get(screen_ir.root.figma_id)
    if root_ir is None or root_clean is None:
        return screen_ir

    def merge_child(
        clean_child: CleanDesignTreeNode, existing: WidgetIrNode | None
    ) -> WidgetIrNode:
        if existing is not None and existing.kind == WidgetIrKind.EXTRACTED:
            if not should_downgrade_extracted_stack(
                existing,
                clean_child,
                extracted_widget_names=extracted_widget_names,
                subtree_root_ids=subtree_root_ids,
            ):
                return existing
            existing = existing.model_copy(
                update={"kind": ir_kind_for_clean_node(clean_child), "ref": None}
            )
        if existing is not None:
            ir_child = existing.model_copy(deep=True)
            if ir_child.kind == WidgetIrKind.EXTRACTED:
                return ir_child
        else:
            ir_child = WidgetIrNode(
                figma_id=clean_child.id, kind=ir_kind_for_clean_node(clean_child)
            )
        if clean_child.type in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW}:
            sync_layout_children(ir_child, clean_child)
        return ir_child

    sync_budget = {"remaining": MAX_SYNC_STACK_IR_NODES}

    def should_sync_clean_child_to_ir(clean_child: CleanDesignTreeNode) -> bool:
        if clean_child.type in STRUCTURAL_IR_SYNC_TYPES:
            return True
        if clean_child.type == NodeType.CONTAINER:
            return container_requires_stack_visual_ir(clean_child)
        return False

    def sync_layout_children(ir_node: WidgetIrNode, clean: CleanDesignTreeNode) -> None:
        if clean.type not in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW}:
            return
        if (
            ir_node.kind == WidgetIrKind.EXTRACTED
            and extracted_reference_valid(ir_node, extracted_widget_names)
        ):
            ir_node.children = []
            return
        existing_by_id = {child.figma_id: child for child in ir_node.children}
        merged: list[WidgetIrNode] = []
        for clean_child in clean.children:
            if clean_child.id in omit or not should_sync_clean_child_to_ir(clean_child):
                continue
            existing = existing_by_id.get(clean_child.id)
            if existing is None and sync_budget["remaining"] <= 0:
                continue
            ir_child = merge_child(clean_child, existing)
            if existing is None:
                sync_budget["remaining"] -= 1
            merged.append(ir_child)
        ir_node.children = merged

    def walk_sync_subtrees(ir_node: WidgetIrNode) -> None:
        clean = tree_by_id.get(ir_node.figma_id)
        if clean is not None and clean.type in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW}:
            sync_layout_children(ir_node, clean)
        for child in ir_node.children:
            walk_sync_subtrees(child)

    walk_sync_subtrees(root_ir)
    return screen_ir


def normalize_screen_ir_presence(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    widget_suffix: str = "Widget",
    extracted_widget_names: frozenset[str] | None = None,
) -> ScreenIr:
    """Deterministically fill large subtrees and stack-placed visuals omitted by the LLM."""
    roots = subtree_root_ids(clean_tree, widget_suffix=widget_suffix)
    before_ids = ir_figma_ids(screen_ir.root)
    screen_ir = ensure_presence_subtrees_in_screen_ir(
        screen_ir, clean_tree, widget_suffix=widget_suffix
    )
    after_subtree_ids = ir_figma_ids(screen_ir.root)
    screen_ir = sync_screen_ir_stack_subtree_from_clean_tree(
        screen_ir,
        clean_tree,
        extracted_widget_names=extracted_widget_names,
        subtree_root_ids=roots,
        widget_suffix=widget_suffix,
    )
    after_sync_ids = ir_figma_ids(screen_ir.root)
    result = ensure_stack_visual_nodes_in_screen_ir(
        screen_ir,
        clean_tree,
        extracted_widget_names=extracted_widget_names,
        subtree_root_ids=roots,
        widget_suffix=widget_suffix,
    )
    after_all_ids = ir_figma_ids(result.root)
    total_added = len(after_all_ids - before_ids)
    if total_added:
        logger.info(
            "IR presence normalized: +{} IR node(s) (subtree {}, structural sync {}, stack-visual {})",
            total_added,
            len(after_subtree_ids - before_ids),
            len(after_sync_ids - after_subtree_ids),
            len(after_all_ids - after_sync_ids),
        )
        if (
            len(after_all_ids - after_sync_ids) > MAX_STACK_VISUAL_IR_INSERTS
            or total_added > MAX_SYNC_STACK_IR_NODES
        ):
            logger.warning(
                "IR presence heavy screen: {} total IR nodes after normalize "
                "(sync cap {}, stack-visual cap {}); decorative stack nodes merge from cleanTree without IR",
                total_added,
                MAX_SYNC_STACK_IR_NODES,
                MAX_STACK_VISUAL_IR_INSERTS,
            )
    from figma_flutter_agent.generator.ir.validate import realign_screen_ir_children_to_clean_tree

    realign_screen_ir_children_to_clean_tree(result, clean_tree)
    return result


def validate_stack_visual_ir_coverage(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
    min_coverage: float = MIN_STACK_VISUAL_IR_COVERAGE,
    widget_suffix: str = "Widget",
    skip_presence_normalize: bool = False,
) -> None:
    """Raise when stack-placed visual IR coverage falls below ``min_coverage``."""
    roots = subtree_root_ids(clean_tree, widget_suffix=widget_suffix)
    if not skip_presence_normalize:
        screen_ir = normalize_screen_ir_presence(
            screen_ir,
            clean_tree,
            extracted_widget_names=extracted_widget_names,
            widget_suffix=widget_suffix,
        )
    tree_by_id = index_clean_tree(clean_tree)
    parent_by_id = build_clean_parent_map(tree_by_id)
    omit = frozenset(screen_ir.omit_figma_ids)
    required = 0
    present = 0
    missing: list[str] = []
    for node_id, node in tree_by_id.items():
        if node_id in omit:
            continue
        if not stack_visual_node_requires_ir(
            node,
            screen_ir=screen_ir,
            node_id=node_id,
            parent_by_id=parent_by_id,
            extracted_widget_names=extracted_widget_names,
            subtree_root_ids=roots,
        ):
            continue
        required += 1
        from figma_flutter_agent.generator.ir.tree import preserve_clean_child_without_ir

        if ir_node_by_figma_id(
            screen_ir.root, node_id
        ) is not None or preserve_clean_child_without_ir(node):
            present += 1
        else:
            missing.append(node_id)
    if required == 0:
        return
    ratio = present / required
    if ratio < min_coverage:
        sample = ", ".join(missing[:8])
        raise GenerationError(
            "screenIr stack-placed visual coverage "
            f"{ratio:.1%} below {min_coverage:.0%} threshold "
            f"({present}/{required} present; missing: {sample})"
        )


__all__ = [
    "SanitizeSummary",
    "expand_extracted_widget_names_for_validate",
    "normalize_screen_ir_presence",
    "sanitize_screen_ir_adaptive_rules",
    "sanitize_screen_ir_duplicate_figma_ids",
    "sanitize_screen_ir_extracted_refs",
    "sanitize_screen_ir_fidelity_authority",
    "sanitize_screen_ir_llm_drift",
    "sanitize_screen_ir_omit_figma_ids",
    "sanitize_screen_ir_phantom_nodes",
    "sanitize_screen_ir_state_by_figma_id",
    "sync_screen_ir_stack_subtree_from_clean_tree",
    "validate_stack_visual_ir_coverage",
]
