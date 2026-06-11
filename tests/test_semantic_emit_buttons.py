"""Semantic emit tests for W1 button templates."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind, WidgetIrNode
from tests.support.semantics_trees import outlined_button, text_button


def _classify_and_stamp(clean, figma_id: str) -> WidgetIrNode:
    screen_ir, _ = classify_screen_ir(default_screen_ir(clean), clean)
    stamped = stamp_fidelity_tiers(screen_ir)
    node = _find_node(stamped.root, figma_id)
    assert node is not None
    return node


def _find_node(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if root.figma_id == figma_id:
        return root
    for child in root.children:
        found = _find_node(child, figma_id)
        if found is not None:
            return found
    return None


def test_outlined_button_emits_outlined_widget_when_verified() -> None:
    clean = outlined_button("btn-outlined-emit")
    ir = _classify_and_stamp(clean, "btn-outlined-emit")
    assert ir.kind == WidgetIrKind.BUTTON_OUTLINED
    ir = ir.model_copy(update={"fidelity_tier": FidelityTier.NATIVE_VERIFIED})
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=clean, parent_type=None, ctx=ctx)
    assert "OutlinedButton" in dart or "CupertinoButton" in dart


def test_text_button_emits_text_widget_when_verified() -> None:
    clean = text_button("btn-text-emit")
    ir = _classify_and_stamp(clean, "btn-text-emit")
    assert ir.kind == WidgetIrKind.BUTTON_TEXT
    ir = ir.model_copy(update={"fidelity_tier": FidelityTier.NATIVE_VERIFIED})
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(ir, clean=clean, parent_type=None, ctx=ctx)
    assert "TextButton" in dart or "CupertinoButton" in dart
