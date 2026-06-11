"""Semantic vs geometric emit comparison helpers (EPIC 3.2)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind, WidgetIrNode


def emit_semantic_path(
    ir: WidgetIrNode,
    *,
    clean,
    ctx: IrEmitContext | None = None,
) -> str:
    """Emit with semantic gates enabled and native_verified tier."""
    effective = ctx or IrEmitContext(uses_svg=False, responsive_enabled=False)
    verified_ir = ir.model_copy(update={"fidelity_tier": FidelityTier.NATIVE_VERIFIED})
    return emit_widget_expression(
        verified_ir,
        clean=clean,
        parent_type=None,
        ctx=IrEmitContext(
            semantic_report_only=False,
            uses_svg=effective.uses_svg,
            responsive_enabled=effective.responsive_enabled,
            theme_variant=effective.theme_variant,
        ),
    )


def emit_geometric_path(
    ir: WidgetIrNode,
    *,
    clean,
    ctx: IrEmitContext | None = None,
) -> str:
    """Emit with report_only gate (geometric fallback)."""
    effective = ctx or IrEmitContext(uses_svg=False, responsive_enabled=False)
    auto_ir = WidgetIrNode(figma_id=ir.figma_id, kind=WidgetIrKind.AUTO)
    return emit_widget_expression(
        auto_ir,
        clean=clean,
        parent_type=None,
        ctx=IrEmitContext(
            semantic_report_only=True,
            uses_svg=effective.uses_svg,
            responsive_enabled=effective.responsive_enabled,
            theme_variant=effective.theme_variant,
        ),
    )
