"""Inner fidelity tier router (EPIC 3.5)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.ir.fidelity_router import (
    EmitPath,
    route_by_fidelity_tier,
    semantic_native_emit_allowed,
)
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind, WidgetIrNode
from tests.support.semantics_trees import filled_button


def test_report_only_skips_native_regardless_of_tier() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    ctx = IrEmitContext(semantic_report_only=True, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=filled_button(), parent_type=None, ctx=ctx)
    assert "ElevatedButton" not in dart and "FilledButton" not in dart


def test_native_verified_uses_template() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=filled_button(), parent_type=None, ctx=ctx)
    assert "ElevatedButton" in dart or "FilledButton" in dart or "CupertinoButton" in dart


def test_native_unverified_falls_back_styled_primitive() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_UNVERIFIED,
    )
    verified = ir.model_copy(update={"fidelity_tier": FidelityTier.NATIVE_VERIFIED})
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart_native = emit_widget_expression(verified, clean=filled_button(), parent_type=None, ctx=ctx)
    dart_styled = emit_widget_expression(ir, clean=filled_button(), parent_type=None, ctx=ctx)
    assert "minimumSize: Size.zero" in dart_native
    assert "Theme.of(context).colorScheme.primary" in dart_styled
    assert "ElevatedButton" not in dart_styled and "FilledButton" not in dart_styled


def test_strict_fidelity_rejects_unverified() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_UNVERIFIED,
    )
    ctx = IrEmitContext()
    with pytest.raises(GenerationError, match="strict_fidelity"):
        route_by_fidelity_tier(ir, ctx=ctx, strict_fidelity=True)


def test_baked_tier_downgrades_live_text_in_dev_profile() -> None:
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.SVG_BAKED,
    )
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=filled_button(), parent_type=None, ctx=ctx)
    assert "Theme.of(context).colorScheme.primary" in dart
    assert "ElevatedButton" not in dart and "FilledButton" not in dart


def test_route_native_verified() -> None:
    ir = WidgetIrNode(
        figma_id="x",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    assert route_by_fidelity_tier(ir, ctx=IrEmitContext(), strict_fidelity=False) == (
        EmitPath.NATIVE_TEMPLATE
    )
    assert semantic_native_emit_allowed(ir, ctx=IrEmitContext(), strict_fidelity=False)


def test_route_styled_primitive_tier() -> None:
    ir = WidgetIrNode(
        figma_id="x",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.STYLED_PRIMITIVE,
    )
    assert route_by_fidelity_tier(ir, ctx=IrEmitContext(), strict_fidelity=False) == (
        EmitPath.STYLED_PRIMITIVE
    )


def test_unsupported_tier_routes_styled_in_dev() -> None:
    ir = WidgetIrNode(
        figma_id="x",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.UNSUPPORTED,
    )
    assert route_by_fidelity_tier(ir, ctx=IrEmitContext(), strict_fidelity=False) == (
        EmitPath.STYLED_PRIMITIVE
    )
