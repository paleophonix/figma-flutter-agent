"""Height unpinning pass for cascaded FIXED column hosts."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.protocol import PassContext
from figma_flutter_agent.generator.ir.passes.provenance_record import record_node_mutation
from figma_flutter_agent.generator.ir.passes.sync import (
    index_ir_nodes,
    update_clean_subtree,
    update_ir_subtree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    HeightFit,
    LayoutBackend,
    LayoutSlotIr,
    NodeType,
    ScreenIr,
    SizingMode,
    WidgetIrKind,
    WidgetIrLayoutHints,
    WidgetIrNode,
)

_BLOCKING_DESCENDANT_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.CARD,
        NodeType.STACK,
        NodeType.ROW,
        NodeType.WRAP,
        NodeType.IMAGE,
        NodeType.VECTOR,
        NodeType.GRID,
    }
)
_TEXT_INPUT_TYPES = frozenset({NodeType.TEXT, NodeType.INPUT})


def _subtree_is_text_or_input_only(node: CleanDesignTreeNode) -> bool:
    if node.type in _BLOCKING_DESCENDANT_TYPES:
        return False
    if not node.children:
        return node.type in _TEXT_INPUT_TYPES
    return all(_subtree_is_text_or_input_only(child) for child in node.children)


def _should_unpin_column(node: CleanDesignTreeNode) -> bool:
    if node.type != NodeType.COLUMN:
        return False
    if node.sizing.height_mode != SizingMode.FIXED:
        return False
    if not node.children:
        return False
    return all(_subtree_is_text_or_input_only(child) for child in node.children)


def _unpin_clean_column(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    if not _should_unpin_column(node):
        return node
    fixed_height = node.sizing.height
    sizing = node.sizing.model_copy(
        update={
            "height_mode": SizingMode.HUG,
            "min_height": fixed_height if fixed_height is not None else node.sizing.min_height,
            "height": None,
        },
    )
    slot = node.layout_slot
    if slot is None:
        slot = LayoutSlotIr()
    slot = slot.model_copy(
        update={
            "backend": LayoutBackend.FLEX,
            "height_fit": HeightFit.MIN,
            "min_height": sizing.min_height,
        },
    )
    return node.model_copy(update={"sizing": sizing, "layout_slot": slot})


def _unpin_ir_column(node: WidgetIrNode, *, min_height: float | None) -> WidgetIrNode:
    hints = node.layout_hints
    if hints is None:
        hints = WidgetIrLayoutHints()
    hints = hints.model_copy(
        update={
            "min_height": min_height,
            "height_fit": HeightFit.MIN.value,
        },
    )
    updated_children = [_unpin_ir_child_text_input(child) for child in node.children]
    return node.model_copy(update={"layout_hints": hints, "children": updated_children})


def _unpin_ir_child_text_input(node: WidgetIrNode) -> WidgetIrNode:
    if node.kind not in {WidgetIrKind.TEXT, WidgetIrKind.INPUT, WidgetIrKind.AUTO}:
        return node
    hints = node.layout_hints
    if hints is None:
        hints = WidgetIrLayoutHints()
    hints = hints.model_copy(update={"height_fit": HeightFit.MIN.value})
    return node.model_copy(update={"layout_hints": hints})


def unpin_cascaded_heights(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    ctx: PassContext | None = None,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Relax cascaded FIXED column heights on both graphs."""
    node_ids: list[str] = []

    def collect(node: CleanDesignTreeNode, *, is_root: bool) -> None:
        if not is_root and _should_unpin_column(node):
            node_ids.append(node.id)
        for child in node.children:
            collect(child, is_root=False)

    collect(clean_tree, is_root=True)

    updated_clean = clean_tree
    updated_ir = screen_ir
    ir_index = index_ir_nodes(screen_ir.root)
    for node_id in node_ids:
        before = _find_clean_node(updated_clean, node_id)
        updated_clean = update_clean_subtree(
            updated_clean,
            node_id,
            _unpin_clean_column,
        )
        after = _find_clean_node(updated_clean, node_id)
        min_height = after.sizing.min_height if after is not None else None
        if ctx is not None and before is not None and after is not None:
            record_node_mutation(
                ctx,
                transform="unpin",
                node_id=node_id,
                field_name="sizing.height_mode",
                old=before.sizing.height_mode.value,
                new=after.sizing.height_mode.value,
            )
            record_node_mutation(
                ctx,
                transform="unpin",
                node_id=node_id,
                field_name="sizing.min_height",
                old=before.sizing.min_height,
                new=after.sizing.min_height,
            )
        if ir_index.get(node_id) is not None:
            updated_ir = updated_ir.model_copy(
                update={
                    "root": update_ir_subtree(
                        updated_ir.root,
                        node_id,
                        lambda node, mh=min_height: _unpin_ir_column(node, min_height=mh),
                    ),
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
