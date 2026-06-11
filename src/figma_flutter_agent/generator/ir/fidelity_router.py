"""Per-node fidelity tier routing for semantic emit (EPIC 3.5)."""

from __future__ import annotations

from enum import StrEnum

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.schemas import FidelityTier, WidgetIrNode


class EmitPath(StrEnum):
    """Resolved emit path for a semantic IR node."""

    NATIVE_TEMPLATE = "native_template"
    GEOMETRIC_FALLBACK = "geometric_fallback"
    BAKED_ASSET = "baked_asset"


def tier_allows_native(tier: FidelityTier | None) -> bool:
    """Return True when tier authorizes native Jinja template emit."""
    return tier == FidelityTier.NATIVE_VERIFIED


def route_by_fidelity_tier(
    ir: WidgetIrNode,
    *,
    ctx: IrEmitContext,
    strict_fidelity: bool,
) -> EmitPath:
    """Select emit path from per-node ``fidelity_tier``."""
    tier = ir.fidelity_tier
    if tier is None or tier == FidelityTier.NATIVE_UNVERIFIED:
        if strict_fidelity and tier == FidelityTier.NATIVE_UNVERIFIED:
            raise GenerationError(
                f"strict_fidelity rejects native_unverified semantic node {ir.figma_id!r} "
                f"(kind={ir.kind.value})"
            )
        return EmitPath.GEOMETRIC_FALLBACK
    if tier == FidelityTier.NATIVE_VERIFIED:
        return EmitPath.NATIVE_TEMPLATE
    if tier in {FidelityTier.SVG_BAKED, FidelityTier.PNG_BAKED}:
        return EmitPath.BAKED_ASSET
    return EmitPath.GEOMETRIC_FALLBACK


def semantic_native_emit_allowed(
    ir: WidgetIrNode,
    *,
    ctx: IrEmitContext,
    strict_fidelity: bool,
) -> bool:
    """Return True when native semantic template emit is allowed for ``ir``."""
    return route_by_fidelity_tier(ir, ctx=ctx, strict_fidelity=strict_fidelity) == (
        EmitPath.NATIVE_TEMPLATE
    )
