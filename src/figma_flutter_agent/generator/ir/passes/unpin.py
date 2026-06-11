"""Height unpinning pass for cascaded FIXED column hosts."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.sync import update_clean_subtree, update_ir_subtree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    HeightFit,
    LayoutBackend,
    LayoutSlotIr,
    NodeType,
    ScreenIr,
    SizingMode,
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


def _unpin_ir_column(node: WidgetIrNode) -> WidgetIrNode:
    hints = node.layout_hints
    if hints is None:
        from figma_flutter_agent.schemas import WidgetIrLayoutHints

        hints = WidgetIrLayoutHints()
    return node.model_copy(update={"kind": node.kind})


def unpin_cascaded_heights(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
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
    for node_id in node_ids:
        updated_clean = update_clean_subtree(
            updated_clean,
            node_id,
            _unpin_clean_column,
        )
        updated_ir = updated_ir.model_copy(
            update={
                "root": update_ir_subtree(updated_ir.root, node_id, _unpin_ir_column),
            },
        )
    return updated_ir, updated_clean
