"""Per-node fidelity tier routing for semantic emit (EPIC 4.5)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.schemas import FidelityTier, WidgetIrNode


class EmitPath(StrEnum):
    """Resolved emit path for a semantic IR node."""

    NATIVE_TEMPLATE = "native_template"
    STYLED_PRIMITIVE = "styled_primitive"
    GEOMETRIC_FALLBACK = "geometric_fallback"
    BAKED_ASSET = "baked_asset"


@dataclass(frozen=True)
class FidelityRoutePolicy:
    """Profile flags that influence fidelity tier routing."""

    strict_fidelity: bool = False
    strict_l10n: bool = False
    strict_a11y: bool = False


def tier_allows_native(tier: FidelityTier | None) -> bool:
    """Return True when tier authorizes native Jinja template emit."""
    return tier == FidelityTier.NATIVE_VERIFIED


def route_by_fidelity_tier(
    ir: WidgetIrNode,
    *,
    ctx: IrEmitContext,
    strict_fidelity: bool,
    strict_l10n: bool = False,
    strict_a11y: bool = False,
) -> EmitPath:
    """Select emit path from per-node ``fidelity_tier`` and profile policy."""
    _ = ctx
    policy = FidelityRoutePolicy(
        strict_fidelity=strict_fidelity,
        strict_l10n=strict_l10n,
        strict_a11y=strict_a11y,
    )
    return route_with_policy(ir, policy=policy)


def route_with_policy(
    ir: WidgetIrNode,
    *,
    policy: FidelityRoutePolicy,
) -> EmitPath:
    """Select emit path using an explicit route policy."""
    tier = ir.fidelity_tier
    if tier is None or tier == FidelityTier.NATIVE_UNVERIFIED:
        if policy.strict_fidelity and tier == FidelityTier.NATIVE_UNVERIFIED:
            return EmitPath.GEOMETRIC_FALLBACK
        return EmitPath.STYLED_PRIMITIVE
    if tier == FidelityTier.NATIVE_VERIFIED:
        return EmitPath.NATIVE_TEMPLATE
    if tier == FidelityTier.STYLED_PRIMITIVE:
        return EmitPath.STYLED_PRIMITIVE
    if tier in {FidelityTier.SVG_BAKED, FidelityTier.PNG_BAKED}:
        return EmitPath.BAKED_ASSET
    if tier == FidelityTier.UNSUPPORTED:
        if policy.strict_fidelity:
            raise GenerationError(
                f"strict_fidelity rejects unsupported semantic node {ir.figma_id!r} "
                f"(kind={ir.kind.value})"
            )
        return EmitPath.STYLED_PRIMITIVE
    return EmitPath.GEOMETRIC_FALLBACK


def semantic_native_emit_allowed(
    ir: WidgetIrNode,
    *,
    ctx: IrEmitContext,
    strict_fidelity: bool,
    strict_l10n: bool = False,
    strict_a11y: bool = False,
) -> bool:
    """Return True when native semantic template emit is allowed for ``ir``."""
    return (
        route_by_fidelity_tier(
            ir,
            ctx=ctx,
            strict_fidelity=strict_fidelity,
            strict_l10n=strict_l10n,
            strict_a11y=strict_a11y,
        )
        == EmitPath.NATIVE_TEMPLATE
    )
