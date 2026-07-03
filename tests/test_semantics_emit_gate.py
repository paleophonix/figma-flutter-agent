"""Emit gate: PolicyDecision is the sole semantic route authority."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.schemas import (
    FidelityTier,
    NodeType,
    WidgetIrKind,
    WidgetIrNode,
)
from tests.support.semantics_trees import filled_button


def test_report_only_skips_semantic_emit_for_classified_button() -> None:
    clean = filled_button()
    baseline_ir = default_screen_ir(clean)
    classified_ir, _ = classify_screen_ir(baseline_ir, clean)
    classified_ir = stamp_fidelity_tiers(classified_ir)
    btn_ir = _find_node(classified_ir.root, "btn-filled")
    assert btn_ir is not None
    assert btn_ir.kind == WidgetIrKind.BUTTON_FILLED
    assert btn_ir.fidelity_tier == FidelityTier.NATIVE_VERIFIED

    ctx_report_only = IrEmitContext(
        uses_svg=False,
        responsive_enabled=False,
        semantic_report_only=True,
    )
    ctx_emit = IrEmitContext(
        uses_svg=False,
        responsive_enabled=False,
        semantic_report_only=False,
    )
    auto_ir = WidgetIrNode(figma_id="btn-filled", kind=WidgetIrKind.AUTO)
    dart_auto = emit_widget_expression(
        auto_ir,
        clean=clean,
        parent_type=NodeType.COLUMN,
        ctx=ctx_report_only,
    )
    dart_classified = emit_widget_expression(
        btn_ir,
        clean=clean,
        parent_type=NodeType.COLUMN,
        ctx=ctx_report_only,
    )
    dart_semantic = emit_widget_expression(
        btn_ir,
        clean=clean,
        parent_type=NodeType.COLUMN,
        ctx=ctx_emit,
    )

    assert dart_classified == dart_auto
    assert dart_semantic != dart_auto
    assert "FilledButton" in dart_semantic or "ElevatedButton" in dart_semantic


def test_verified_native_emit_uses_native_template() -> None:
    clean = filled_button()
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.NATIVE_VERIFIED,
    )
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=clean, parent_type=NodeType.COLUMN, ctx=ctx)
    assert "FilledButton" in dart or "ElevatedButton" in dart


def test_styled_tier_emit_uses_styled_primitive() -> None:
    clean = filled_button()
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_FILLED,
        fidelity_tier=FidelityTier.STYLED_PRIMITIVE,
    )
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=clean, parent_type=NodeType.COLUMN, ctx=ctx)
    assert "Theme.of(context).colorScheme.primary" in dart
    assert "FilledButton" not in dart and "ElevatedButton" not in dart


def test_baked_tier_emit_uses_asset_path() -> None:
    from figma_flutter_agent.schemas import CleanDesignTreeNode, Sizing, SizingMode

    clean = CleanDesignTreeNode(
        id="btn-filled",
        name="icon",
        type=NodeType.VECTOR,
        sizing=Sizing(width=24.0, height=24.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED),
        vector_asset_key="assets/icons/star.svg",
    )
    ir = WidgetIrNode(
        figma_id="btn-filled",
        kind=WidgetIrKind.BUTTON_ICON,
        fidelity_tier=FidelityTier.SVG_BAKED,
    )
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=True, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=clean, parent_type=NodeType.COLUMN, ctx=ctx)
    assert "SvgPicture.asset(" in dart


def _find_node(node: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if node.figma_id == figma_id:
        return node
    for child in node.children:
        found = _find_node(child, figma_id)
        if found is not None:
            return found
    return None
