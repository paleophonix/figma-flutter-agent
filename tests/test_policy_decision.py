"""PolicyDecision wrapper tests (Program 03 P0-3)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.fidelity.router import EmitPath
from figma_flutter_agent.generator.ir.policy import (
    UNMIGRATED_EMIT_ROUTES,
    resolve_policy_decision,
)
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind, WidgetIrNode


def test_resolve_policy_blocks_native_when_report_only() -> None:
    ir = WidgetIrNode(
        figma_id="1:btn",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    ctx = IrEmitContext(semantic_report_only=True)
    decision = resolve_policy_decision(ir, ctx=ctx)
    assert decision.report_only is True
    assert decision.native_emit_allowed is False


def test_resolve_policy_allows_native_when_verified() -> None:
    ir = WidgetIrNode(
        figma_id="1:btn",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    ctx = IrEmitContext(semantic_report_only=False)
    decision = resolve_policy_decision(ir, ctx=ctx)
    assert decision.emit_path == EmitPath.NATIVE_TEMPLATE
    assert decision.native_emit_allowed is True


def test_unmigrated_routes_documented() -> None:
    assert "generator/layout/widgets/emit/dispatch.py" in UNMIGRATED_EMIT_ROUTES
