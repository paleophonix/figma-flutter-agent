"""Extracted widget bodies use IR-primary emit (EPIC 3.1)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.extracted import emit_extracted_widget_code_from_ir
from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from tests.support.semantics_trees import filled_button


def test_extracted_widget_semantic_emit_when_enabled() -> None:
    clean = CleanDesignTreeNode(
        id="root",
        name="root",
        type=NodeType.COLUMN,
        children=[filled_button()],
    )
    baseline = default_screen_ir(clean)
    classified, _ = classify_screen_ir(
        baseline,
        clean,
        confidence_threshold=0.8,
        grey_zone_min=0.5,
        authoritative_classifier=True,
        llm_gray_zone_enabled=False,
    )
    stamped = stamp_fidelity_tiers(classified)
    widget_ir = next(
        child for child in stamped.root.children if child.figma_id == "btn-filled"
    )
    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_extracted_widget_code_from_ir(
        widget_ir,
        clean_tree=clean,
        widget_name="primary_button",
        ctx=ctx,
    )
    assert "ElevatedButton" in dart or "FilledButton" in dart or "CupertinoButton" in dart
