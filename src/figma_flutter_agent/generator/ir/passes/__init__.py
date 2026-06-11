"""Deterministic IR layout passes with dual-graph synchronization."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.manager import (
    PassManager,
    run_ir_classification_passes,
    run_ir_layout_passes,
)
from figma_flutter_agent.generator.ir.passes.protocol import Pass, PassContext
from figma_flutter_agent.generator.ir.passes.registry import WAVE_1_IR_PASSES
from figma_flutter_agent.generator.ir.passes.scroll_host import inject_scroll_host
from figma_flutter_agent.generator.ir.passes.semantic import SEMANTIC_PASSES
from figma_flutter_agent.generator.ir.passes.unpin import unpin_cascaded_heights
from figma_flutter_agent.generator.ir.passes.unstack import unstack_homogeneous_stack
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr


def apply_ir_layout_passes(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    macro_height_threshold_px: int = 900,
    inject_root_scroll_host: bool = False,
    validate_cp2: bool = True,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Run layout optimization passes with symmetric IR and clean-tree updates.

    Args:
        screen_ir: LLM or blueprint screen IR graph.
        clean_tree: Parsed clean design tree for the same screen.
        macro_height_threshold_px: Root extent above this triggers scroll host.
        inject_root_scroll_host: When False (default), preserve layout-root responsive shells.
        validate_cp2: When true, run conservation checkpoint after passes.

    Returns:
        Updated ``(screen_ir, clean_tree)`` pair safe for legacy emit.
    """
    return run_ir_layout_passes(
        screen_ir,
        clean_tree,
        macro_height_threshold_px=macro_height_threshold_px,
        inject_root_scroll_host=inject_root_scroll_host,
        validate_cp2=validate_cp2,
    )


def apply_ir_classification_passes(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    validate_cp2: bool = True,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Run semantic classification passes with CP2 conservation validation."""
    return run_ir_classification_passes(
        screen_ir,
        clean_tree,
        validate_cp2=validate_cp2,
    )


__all__ = [
    "Pass",
    "PassContext",
    "PassManager",
    "SEMANTIC_PASSES",
    "WAVE_1_IR_PASSES",
    "apply_ir_classification_passes",
    "apply_ir_layout_passes",
    "inject_scroll_host",
    "unpin_cascaded_heights",
    "unstack_homogeneous_stack",
]
