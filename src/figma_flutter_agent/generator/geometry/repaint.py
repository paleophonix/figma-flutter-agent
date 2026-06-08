"""Repaint-boundary run-length planning."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, LayerClass, NodeType, WrapKind


def apply_repaint_rle(root: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """RLE static runs under stack parents (T5)."""

    def visit(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [visit(child) for child in node.children]
        working = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK or not children:
            return working
        updated: list[CleanDesignTreeNode] = []
        run_start: int | None = None
        for index, child in enumerate(children):
            slot = child.layout_slot
            is_static = slot is not None and slot.layer_class == LayerClass.STATIC
            if is_static:
                if run_start is None:
                    run_start = index
                updated.append(child)
                continue
            if run_start is not None:
                _add_repaint_boundary_wraps(updated, run_start=run_start, run_end=index)
                run_start = None
            updated.append(child)
        if run_start is not None:
            _add_repaint_boundary_wraps(
                updated,
                run_start=run_start,
                run_end=len(updated),
            )
        return working.model_copy(update={"children": updated})

    return visit(root)


def _add_repaint_boundary_wraps(
    children: list[CleanDesignTreeNode],
    *,
    run_start: int,
    run_end: int,
) -> None:
    for run_index in range(run_start, run_end):
        run_child = children[run_index]
        run_slot = run_child.layout_slot
        if run_slot is None:
            continue
        run_wraps = tuple(dict.fromkeys((*run_slot.wraps, WrapKind.REPAINT_BOUNDARY)))
        children[run_index] = run_child.model_copy(
            update={"layout_slot": run_slot.model_copy(update={"wraps": run_wraps})}
        )
