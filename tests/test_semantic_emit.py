"""Tests for semantic Jinja2 widget emission."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.semantic_emit import emit_semantic_widget
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrKind, WidgetIrNode


def test_chip_choice_emits_material_widget() -> None:
    clean = CleanDesignTreeNode(
        id="chip-1",
        name="chip",
        type=NodeType.BUTTON,
        text="500",
    )
    ir = WidgetIrNode(figma_id="chip-1", kind=WidgetIrKind.CHIP_CHOICE, is_selected=True)
    dart = emit_semantic_widget(ir, clean=clean, ctx=IrEmitContext())
    assert "ChoiceChip(" in dart
    assert "selected: true" in dart
    assert "'500'" in dart
