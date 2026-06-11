"""Styled primitive emit path (EPIC 4.5)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.ir.fidelity import EmitPath, route_by_fidelity_tier
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind, WidgetIrNode
from tests.support.semantics_trees import filled_button


def test_native_unverified_routes_to_styled_primitive() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_UNVERIFIED,
    )
    assert route_by_fidelity_tier(ir, ctx=IrEmitContext(), strict_fidelity=False) == (
        EmitPath.STYLED_PRIMITIVE
    )


def test_styled_primitive_uses_theme_not_native_template() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_UNVERIFIED,
    )
    verified = ir.model_copy(update={"fidelity_tier": FidelityTier.NATIVE_VERIFIED})
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart_native = emit_widget_expression(verified, clean=filled_button(), parent_type=None, ctx=ctx)
    dart_styled = emit_widget_expression(ir, clean=filled_button(), parent_type=None, ctx=ctx)
    assert "Theme.of(context).colorScheme.primary" in dart_styled
    assert "minimumSize: Size.zero" in dart_native
    assert "minimumSize: Size.zero" not in dart_styled
    assert "ElevatedButton" not in dart_styled and "FilledButton" not in dart_styled


def test_styled_primitive_tier_emits_themed_shell() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.STYLED_PRIMITIVE,
    )
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=filled_button(), parent_type=None, ctx=ctx)
    assert "Theme.of(context).colorScheme.primary" in dart
