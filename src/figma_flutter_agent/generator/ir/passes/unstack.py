"""Unstacking pass: false STACK rows to ROW/COLUMN/WRAP."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.layout_criteria import (
    LayoutActivationDecision,
    evaluate_stack_flex_candidate,
)
from figma_flutter_agent.generator.ir.passes.protocol import PassContext
from figma_flutter_agent.generator.ir.passes.provenance_record import record_node_mutation
from figma_flutter_agent.generator.ir.passes.sync import (
    index_ir_nodes,
    ir_kind_for_node_type,
    update_clean_subtree,
    update_ir_subtree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ScreenIr,
    WidgetIrKind,
    WidgetIrLayoutHints,
    WidgetIrNode,
)


def _clear_child_placements(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    cleared = [child.model_copy(update={"stack_placement": None}) for child in node.children]
    return node.model_copy(update={"children": cleared})


def _apply_unstack_to_clean(
    node: CleanDesignTreeNode,
    decision: LayoutActivationDecision,
) -> CleanDesignTreeNode:
    if not decision.activated or decision.target_type is None:
        return node
    updated = _clear_child_placements(node)
    gap_mode = decision.gap_mode or "uniform"
    spacing = decision.spacing if gap_mode == "uniform" else 0.0
    explicit = list(decision.explicit_gaps) if decision.explicit_gaps else None
    return updated.model_copy(
        update={
            "type": decision.target_type,
            "spacing": spacing,
            "layout_positioning": "AUTO",
            "flex_gap_mode": gap_mode,
            "flex_explicit_gaps": explicit,
        },
    )


def _apply_unstack_to_ir(
    node: WidgetIrNode,
    decision: LayoutActivationDecision,
) -> WidgetIrNode:
    if not decision.activated or decision.target_type is None:
        return node
    kind = ir_kind_for_node_type(decision.target_type.value)
    gap_mode = decision.gap_mode or "uniform"
    hints = WidgetIrLayoutHints(
        flex_spacing=decision.spacing if gap_mode == "uniform" else 0.0,
        gap_mode=gap_mode,
        explicit_gaps=list(decision.explicit_gaps) if decision.explicit_gaps else None,
    )
    if node.kind == WidgetIrKind.STACK or node.kind == WidgetIrKind.AUTO:
        return node.model_copy(update={"kind": kind, "layout_hints": hints})
    return node.model_copy(update={"layout_hints": hints})


def _record_unstack_provenance(
    ctx: PassContext | None,
    *,
    node_id: str,
    before: CleanDesignTreeNode,
    after: CleanDesignTreeNode,
    decision: LayoutActivationDecision,
) -> None:
    if ctx is None:
        return
    record_node_mutation(
        ctx,
        transform="unstack",
        node_id=node_id,
        field_name="type",
        old=before.type.value,
        new=after.type.value,
    )
    if before.spacing != after.spacing:
        record_node_mutation(
            ctx,
            transform="unstack",
            node_id=node_id,
            field_name="spacing",
            old=before.spacing,
            new=after.spacing,
        )
    if before.flex_gap_mode != after.flex_gap_mode:
        record_node_mutation(
            ctx,
            transform="unstack",
            node_id=node_id,
            field_name="flex_gap_mode",
            old=before.flex_gap_mode,
            new=after.flex_gap_mode,
        )
    record_node_mutation(
        ctx,
        transform="unstack",
        node_id=node_id,
        field_name="layout_evidence",
        old=None,
        new=decision.evidence,
    )


def unstack_homogeneous_stack(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    ctx: PassContext | None = None,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Transform false stacks into ROW/COLUMN/WRAP on both graphs."""
    ir_index = index_ir_nodes(screen_ir.root)
    stack_ids: list[str] = []

    def collect(node: CleanDesignTreeNode) -> None:
        decision = evaluate_stack_flex_candidate(node)
        if decision.activated:
            stack_ids.append(node.id)
        for child in node.children:
            collect(child)

    collect(clean_tree)

    updated_clean = clean_tree
    updated_ir = screen_ir
    for node_id in stack_ids:
        clean_node = _find_clean_node(updated_clean, node_id)
        if clean_node is None:
            continue
        decision = evaluate_stack_flex_candidate(clean_node)
        if not decision.activated:
            continue

        def clean_updater(
            node: CleanDesignTreeNode,
            *,
            _decision: LayoutActivationDecision = decision,
        ) -> CleanDesignTreeNode:
            return _apply_unstack_to_clean(node, _decision)

        before = clean_node
        updated_clean = update_clean_subtree(updated_clean, node_id, clean_updater)
        after = _find_clean_node(updated_clean, node_id)
        if after is not None:
            _record_unstack_provenance(ctx, node_id=node_id, before=before, after=after, decision=decision)

        ir_node = ir_index.get(node_id)
        if ir_node is not None:

            def ir_updater(
                node: WidgetIrNode,
                *,
                _decision: LayoutActivationDecision = decision,
            ) -> WidgetIrNode:
                return _apply_unstack_to_ir(node, _decision)

            updated_ir = updated_ir.model_copy(
                update={
                    "root": update_ir_subtree(updated_ir.root, node_id, ir_updater),
                },
            )
            ir_index = index_ir_nodes(updated_ir.root)

    return updated_ir, updated_clean


def _find_clean_node(
    root: CleanDesignTreeNode,
    node_id: str,
) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_clean_node(child, node_id)
        if found is not None:
            return found
    return None
