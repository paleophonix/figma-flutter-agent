"""PassManager orchestration for registered IR layout passes."""

from __future__ import annotations

from figma_flutter_agent.debug.provenance import ProvenanceRecorder
from figma_flutter_agent.generator.ir.passes.protocol import Pass, PassContext
from figma_flutter_agent.generator.ir.passes.registry import WAVE_1_IR_PASSES
from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr


class PassManager:
    """Runs registered passes with CP2 conservation validation."""

    def __init__(
        self,
        passes: tuple[Pass, ...] = WAVE_1_IR_PASSES,
        *,
        checkpoint: str = "CP2_ir_passes",
    ) -> None:
        self._passes = passes
        self._checkpoint = checkpoint

    def run(
        self,
        screen_ir: ScreenIr,
        clean_tree: CleanDesignTreeNode,
        *,
        macro_height_threshold_px: int = 900,
        inject_root_scroll_host: bool = False,
        validate_cp2: bool = True,
    ) -> tuple[ScreenIr, CleanDesignTreeNode]:
        """Execute all registered passes in order.

        Args:
            screen_ir: Screen IR graph.
            clean_tree: Parsed clean design tree.
            macro_height_threshold_px: Scroll-host threshold.
            inject_root_scroll_host: Whether scroll host may wrap the layout root.
            validate_cp2: When true, run conservation checkpoint after all passes.

        Returns:
            Updated ``(screen_ir, clean_tree)`` pair.
        """
        from figma_flutter_agent.debug.provenance import get_provenance_recorder
        from figma_flutter_agent.generator.ir.validate.graph import (
            sync_screen_ir_graph_to_clean_tree,
        )

        sync_screen_ir_graph_to_clean_tree(screen_ir, clean_tree)
        baseline_clean = deep_copy_clean_tree(clean_tree)
        baseline_ir = screen_ir.model_copy(deep=True)
        ctx = PassContext(
            screen_ir=screen_ir,
            clean_tree=clean_tree,
            macro_height_threshold_px=macro_height_threshold_px,
            inject_root_scroll_host=inject_root_scroll_host,
            provenance=get_provenance_recorder(),
            checkpoint=self._checkpoint,
        )
        for registered in self._passes:
            before_clean = deep_copy_clean_tree(ctx.clean_tree)
            ctx = registered.run(ctx)
            self._record_pass_mutations(
                registered.name,
                before_clean,
                ctx.clean_tree,
                recorder=ctx.provenance,
                checkpoint=self._checkpoint,
            )
        if validate_cp2:
            from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
                run_cp2_ir_passes,
            )

            run_cp2_ir_passes(baseline_clean, baseline_ir, ctx.clean_tree, ctx.screen_ir)
        return ctx.screen_ir, ctx.clean_tree

    @staticmethod
    def _record_pass_mutations(
        pass_name: str,
        before: CleanDesignTreeNode,
        after: CleanDesignTreeNode,
        *,
        recorder: ProvenanceRecorder | None,
        checkpoint: str = "CP2_ir_passes",
    ) -> None:
        """Record coarse child-count mutations for provenance."""
        if recorder is None:
            return
        before_counts = _child_counts(before)
        after_counts = _child_counts(after)
        for node_id, old_count in before_counts.items():
            new_count = after_counts.get(node_id, 0)
            if old_count != new_count:
                recorder.record_mutation(
                    checkpoint=checkpoint,
                    transform=pass_name,
                    node_id=node_id,
                    field="children_count",
                    old=old_count,
                    new=new_count,
                )


def _child_counts(root: CleanDesignTreeNode) -> dict[str, int]:
    counts: dict[str, int] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        counts[node.id] = len(node.children)
        for child in node.children:
            walk(child)

    walk(root)
    return counts


_DEFAULT_MANAGER = PassManager()
_SEMANTIC_MANAGER = None


def _semantic_manager() -> PassManager:
    global _SEMANTIC_MANAGER
    if _SEMANTIC_MANAGER is None:
        from figma_flutter_agent.generator.ir.passes.semantic import SEMANTIC_PASSES

        _SEMANTIC_MANAGER = PassManager(SEMANTIC_PASSES, checkpoint="CP2_semantic")
    return _SEMANTIC_MANAGER


def run_ir_layout_passes(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    macro_height_threshold_px: int = 900,
    inject_root_scroll_host: bool = False,
    validate_cp2: bool = True,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Module-level entry for IR layout passes via the default manager."""
    return _DEFAULT_MANAGER.run(
        screen_ir,
        clean_tree,
        macro_height_threshold_px=macro_height_threshold_px,
        inject_root_scroll_host=inject_root_scroll_host,
        validate_cp2=validate_cp2,
    )


def run_ir_classification_passes(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    validate_cp2: bool = True,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Run semantic classification passes after layout passes."""
    return _semantic_manager().run(
        screen_ir,
        clean_tree,
        validate_cp2=validate_cp2,
    )
