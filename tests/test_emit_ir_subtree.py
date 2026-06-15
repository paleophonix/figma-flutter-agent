"""Screen-level IR-primary emit (EPIC 3.1)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers
from figma_flutter_agent.generator.ir.screen import emit_screen_code_from_ir
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind, WidgetIrNode
from tests.support.semantics_trees import filled_button, weekday_chip_row


def _classify_and_stamp(clean, screen_ir):
    classified, _ = classify_screen_ir(
        screen_ir,
        clean,
        confidence_threshold=0.8,
        grey_zone_min=0.5,
        authoritative_classifier=True,
        llm_gray_zone_enabled=False,
    )
    return stamp_fidelity_tiers(classified)


def test_screen_semantic_button_when_emit_enabled() -> None:
    clean = filled_button()
    screen_ir = _classify_and_stamp(clean, default_screen_ir(clean))
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_screen_code_from_ir(
        screen_ir,
        clean_tree=clean,
        screen_class="TestScreen",
        ctx=ctx,
        use_scaffold=False,
    )
    assert "ElevatedButton" in dart or "FilledButton" in dart or "CupertinoButton" in dart


def test_report_only_screen_invariant_e25_i() -> None:
    clean = filled_button()
    auto_ir = default_screen_ir(clean)
    classified_ir = _classify_and_stamp(clean, auto_ir)
    ctx_report = IrEmitContext(semantic_report_only=True, uses_svg=False, responsive_enabled=False)
    ctx_emit = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart_auto = emit_screen_code_from_ir(
        auto_ir,
        clean_tree=clean,
        screen_class="TestScreen",
        ctx=ctx_report,
        use_scaffold=False,
    )
    dart_classified_report = emit_screen_code_from_ir(
        classified_ir,
        clean_tree=clean,
        screen_class="TestScreen",
        ctx=ctx_report,
        use_scaffold=False,
    )
    assert dart_classified_report == dart_auto
    dart_semantic = emit_screen_code_from_ir(
        classified_ir,
        clean_tree=clean,
        screen_class="TestScreen",
        ctx=ctx_emit,
        use_scaffold=False,
    )
    assert dart_semantic != dart_auto


def test_isolated_emit_gate_unchanged() -> None:
    clean = filled_button()
    classified_ir = _classify_and_stamp(clean, default_screen_ir(clean))
    btn_ir = _find_node(classified_ir.root, "btn-filled")
    assert btn_ir is not None
    assert btn_ir.kind == WidgetIrKind.BUTTON_FILLED
    assert btn_ir.fidelity_tier == FidelityTier.NATIVE_VERIFIED
    ctx_report = IrEmitContext(semantic_report_only=True, uses_svg=False, responsive_enabled=False)
    ctx_emit = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    auto_ir = WidgetIrNode(figma_id="btn-filled", kind=WidgetIrKind.AUTO)
    dart_auto = emit_widget_expression(
        auto_ir,
        clean=clean,
        parent_type=None,
        ctx=ctx_report,
    )
    dart_classified = emit_widget_expression(
        btn_ir,
        clean=clean,
        parent_type=None,
        ctx=ctx_report,
    )
    dart_semantic = emit_widget_expression(
        btn_ir,
        clean=clean,
        parent_type=None,
        ctx=ctx_emit,
    )
    assert dart_classified == dart_auto
    assert dart_semantic != dart_auto


def test_classified_chip_row_emits_native_chip_host() -> None:
    clean = weekday_chip_row()
    screen_ir = _classify_and_stamp(clean, default_screen_ir(clean))
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_screen_code_from_ir(
        screen_ir,
        clean_tree=clean,
        screen_class="ChipRowScreen",
        ctx=ctx,
        use_scaffold=False,
    )
    assert "ChoiceChip(" in dart


def test_ir_walk_row_shell_for_auto_layout() -> None:
    clean = weekday_chip_row()
    screen_ir = default_screen_ir(clean)
    ctx = IrEmitContext(semantic_report_only=True, uses_svg=False, responsive_enabled=False)
    dart = emit_screen_code_from_ir(
        screen_ir,
        clean_tree=clean,
        screen_class="ChipRowScreen",
        ctx=ctx,
        use_scaffold=False,
    )
    assert "Row(" in dart


def _find_node(node: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if node.figma_id == figma_id:
        return node
    for child in node.children:
        found = _find_node(child, figma_id)
        if found is not None:
            return found
    return None
