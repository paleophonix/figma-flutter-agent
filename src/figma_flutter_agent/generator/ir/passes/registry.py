"""Wave-1 IR pass registry (dual-graph layout passes only)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.protocol import (
    Pass,
    PassContext,
    pass_from_callable,
)
from figma_flutter_agent.generator.ir.passes.scroll_host import inject_scroll_host
from figma_flutter_agent.generator.ir.passes.sectionize import sectionize_root_stack
from figma_flutter_agent.generator.ir.passes.unpin import unpin_cascaded_heights
from figma_flutter_agent.generator.ir.passes.unstack import unstack_homogeneous_stack

_SECTIONIZE_MUTATES = frozenset(
    {
        "type",
        "layout_positioning",
        "scroll_axis",
        "spacing",
        "flex_gap_mode",
        "flex_explicit_gaps",
        "stack_placement",
        "layout_role",
        "children",
        "kind",
        "layout_hints",
    },
)
_SECTIONIZE_PRESERVES = frozenset({"node_multiset", "stack_paint_order", "graph_sync"})

_UNSTACK_MUTATES = frozenset(
    {
        "type",
        "spacing",
        "stack_placement",
        "kind",
        "layout_hints",
        "layout_positioning",
        "flex_gap_mode",
        "flex_explicit_gaps",
    },
)
_UNSTACK_PRESERVES = frozenset({"node_multiset", "stack_paint_order", "graph_sync"})

_UNPIN_MUTATES = frozenset({"sizing", "layout_slot", "layout_hints"})
_UNPIN_PRESERVES = frozenset(
    {"node_multiset", "stack_paint_order", "graph_sync", "kind"}
)

_SCROLL_MUTATES = frozenset({"scroll_axis", "sizing", "kind", "layout_hints"})
_SCROLL_PRESERVES = frozenset({"node_multiset", "stack_paint_order", "graph_sync"})


def _run_sectionize(ctx: PassContext) -> PassContext:
    updated_ir, updated_clean = sectionize_root_stack(
        ctx.screen_ir,
        ctx.clean_tree,
        responsive_reflow_enabled=ctx.responsive_reflow_enabled,
        ctx=ctx,
    )
    return ctx.with_trees(updated_ir, updated_clean)


def _run_unstack(ctx: PassContext) -> PassContext:
    updated_ir, updated_clean = unstack_homogeneous_stack(
        ctx.screen_ir,
        ctx.clean_tree,
        ctx=ctx,
    )
    return ctx.with_trees(updated_ir, updated_clean)


def _run_unpin(ctx: PassContext) -> PassContext:
    updated_ir, updated_clean = unpin_cascaded_heights(
        ctx.screen_ir,
        ctx.clean_tree,
        ctx=ctx,
    )
    return ctx.with_trees(updated_ir, updated_clean)


def _run_scroll_host(ctx: PassContext) -> PassContext:
    updated_ir, updated_clean = inject_scroll_host(
        ctx.screen_ir,
        ctx.clean_tree,
        macro_height_threshold_px=ctx.macro_height_threshold_px,
        inject_at_root=ctx.inject_root_scroll_host,
        ctx=ctx,
    )
    return ctx.with_trees(updated_ir, updated_clean)


WAVE_1_IR_PASSES: tuple[Pass, ...] = (
    pass_from_callable(
        "sectionize",
        _run_sectionize,
        mutates=_SECTIONIZE_MUTATES,
        preserves=_SECTIONIZE_PRESERVES,
    ),
    pass_from_callable(
        "unstack",
        _run_unstack,
        mutates=_UNSTACK_MUTATES,
        preserves=_UNSTACK_PRESERVES,
    ),
    pass_from_callable(
        "unpin",
        _run_unpin,
        mutates=_UNPIN_MUTATES,
        preserves=_UNPIN_PRESERVES,
    ),
    pass_from_callable(
        "scroll_host",
        _run_scroll_host,
        mutates=_SCROLL_MUTATES,
        preserves=_SCROLL_PRESERVES,
    ),
)
