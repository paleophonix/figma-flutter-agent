"""Wave-1 IR pass registry (dual-graph layout passes only)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.protocol import Pass, PassContext, pass_from_callable
from figma_flutter_agent.generator.ir.passes.scroll_host import inject_scroll_host
from figma_flutter_agent.generator.ir.passes.unpin import unpin_cascaded_heights
from figma_flutter_agent.generator.ir.passes.unstack import unstack_homogeneous_stack


def _run_unstack(ctx: PassContext) -> PassContext:
    updated_ir, updated_clean = unstack_homogeneous_stack(ctx.screen_ir, ctx.clean_tree)
    return ctx.with_trees(updated_ir, updated_clean)


def _run_unpin(ctx: PassContext) -> PassContext:
    updated_ir, updated_clean = unpin_cascaded_heights(ctx.screen_ir, ctx.clean_tree)
    return ctx.with_trees(updated_ir, updated_clean)


def _run_scroll_host(ctx: PassContext) -> PassContext:
    updated_ir, updated_clean = inject_scroll_host(
        ctx.screen_ir,
        ctx.clean_tree,
        macro_height_threshold_px=ctx.macro_height_threshold_px,
        inject_at_root=ctx.inject_root_scroll_host,
    )
    return ctx.with_trees(updated_ir, updated_clean)


WAVE_1_IR_PASSES: tuple[Pass, ...] = (
    pass_from_callable("unstack", _run_unstack),
    pass_from_callable("unpin", _run_unpin),
    pass_from_callable("scroll_host", _run_scroll_host),
)
