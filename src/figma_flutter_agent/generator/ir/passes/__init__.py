"""Deterministic IR layout passes with dual-graph synchronization."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.scroll_host import inject_scroll_host
from figma_flutter_agent.generator.ir.passes.unpin import unpin_cascaded_heights
from figma_flutter_agent.generator.ir.passes.unstack import unstack_homogeneous_stack
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr


def apply_ir_layout_passes(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    macro_height_threshold_px: int = 900,
    inject_root_scroll_host: bool = False,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Run layout optimization passes with symmetric IR and clean-tree updates.

    Args:
        screen_ir: LLM or blueprint screen IR graph.
        clean_tree: Parsed clean design tree for the same screen.
        macro_height_threshold_px: Root extent above this triggers scroll host.
        inject_root_scroll_host: When False (default), preserve layout-root responsive shells.

    Returns:
        Updated ``(screen_ir, clean_tree)`` pair safe for legacy emit.
    """
    working_ir = screen_ir
    working_clean = clean_tree

    working_ir, working_clean = unstack_homogeneous_stack(working_ir, working_clean)
    working_ir, working_clean = unpin_cascaded_heights(working_ir, working_clean)
    working_ir, working_clean = inject_scroll_host(
        working_ir,
        working_clean,
        macro_height_threshold_px=macro_height_threshold_px,
        inject_at_root=inject_root_scroll_host,
    )
    return working_ir, working_clean


__all__ = [
    "apply_ir_layout_passes",
    "inject_scroll_host",
    "unpin_cascaded_heights",
    "unstack_homogeneous_stack",
]
