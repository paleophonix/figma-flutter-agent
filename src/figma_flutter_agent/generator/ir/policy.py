"""Emit policy decision wrapper (Program 03 P0-3)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.fidelity.router import (
    EmitPath,
    route_by_fidelity_tier,
    tier_allows_native,
)
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind, WidgetIrNode

# Routes not yet migrated to PolicyDecision (P0 documents only):
UNMIGRATED_EMIT_ROUTES: tuple[str, ...] = (
    "generator/layout/widgets/emit/dispatch.py",
    "generator/layout/widgets/emit/flex.py",
    "generator/layout/widgets/emit/stack.py",
    "generator/layout/widgets/emit/controls.py",
    "generator/layout/widgets/option_chip.py",
    "generator/layout/choice_chip_row.py",
    "generator/ir/semantic_emit.py",
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Snapshot of classify → stamp → emit gate for one IR node."""

    report_only: bool
    classification_kind: WidgetIrKind
    authoritative_classifier: bool
    fidelity_tier: FidelityTier | None
    emit_path: EmitPath
    native_emit_allowed: bool


def resolve_policy_decision(
    ir: WidgetIrNode,
    *,
    ctx: IrEmitContext,
) -> PolicyDecision:
    """Resolve emit policy from report_only, classification, and fidelity tier."""
    semantics = ctx.semantics
    report_only = (
        ctx.semantic_report_only
        if ctx.semantic_report_only is not None
        else semantics.report_only
    )
    emit_path = route_by_fidelity_tier(
        ir,
        ctx=ctx,
        strict_fidelity=semantics.strict_fidelity,
        strict_l10n=semantics.strict_l10n,
        strict_a11y=semantics.strict_a11y,
    )
    authoritative = semantics.authoritative_classifier
    native_allowed = (
        not report_only
        and authoritative
        and tier_allows_native(ir.fidelity_tier)
        and emit_path == EmitPath.NATIVE_TEMPLATE
    )
    return PolicyDecision(
        report_only=report_only,
        classification_kind=ir.kind,
        authoritative_classifier=authoritative,
        fidelity_tier=ir.fidelity_tier,
        emit_path=emit_path,
        native_emit_allowed=native_allowed,
    )
