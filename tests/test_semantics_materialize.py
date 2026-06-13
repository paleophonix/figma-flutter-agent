"""Materialize pipeline invokes semantic classification after layout passes."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.materialize import materialize_screen_code_from_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FlutterGenerationResponse,
    NodeType,
    ScreenIr,
    WidgetIrNode,
)


def test_materialize_runs_classification_after_layout() -> None:
    clean = CleanDesignTreeNode(id="root", name="root", type=NodeType.COLUMN)
    screen_ir = ScreenIr(root=WidgetIrNode(figma_id="root"))
    generation = FlutterGenerationResponse(screen_ir=screen_ir, extracted_widgets=[])
    ctx = IrEmitContext(policy=type("P", (), {"validate": False, "apply_guards": False})())

    calls: list[str] = []

    def _layout(*args, **kwargs):
        calls.append("layout")
        return screen_ir, clean

    def _classify(*args, **kwargs):
        calls.append("classify")
        return screen_ir, clean

    with (
        patch(
            "figma_flutter_agent.generator.ir.passes.apply_ir_layout_passes",
            side_effect=_layout,
        ),
        patch(
            "figma_flutter_agent.generator.ir.passes.apply_ir_classification_passes",
            side_effect=_classify,
        ),
        patch(
            "figma_flutter_agent.generator.ir.materialize.emit_screen_code_from_ir",
            return_value="class S {}",
        ),
    ):
        materialize_screen_code_from_ir(
            generation,
            clean_tree=clean,
            feature_name="demo",
            ctx=ctx,
            materialize_extracted=False,
        )

    assert calls == ["layout", "classify"]


def test_materialize_stamp_fidelity_uses_ctx_semantics_flags() -> None:
    clean = CleanDesignTreeNode(id="root", name="root", type=NodeType.COLUMN)
    screen_ir = ScreenIr(root=WidgetIrNode(figma_id="root"))
    generation = FlutterGenerationResponse(screen_ir=screen_ir, extracted_widgets=[])
    ctx = IrEmitContext(
        policy=type("P", (), {"validate": False, "apply_guards": False})(),
        strict_fidelity=True,
        strict_l10n=True,
        strict_a11y=True,
    )
    captured: dict[str, bool] = {}

    def _layout(*args, **kwargs):
        return screen_ir, clean

    def _classify(*args, **kwargs):
        return screen_ir, clean

    def _stamp(screen_ir, *, strict_fidelity, strict_l10n, strict_a11y, **kwargs):
        captured["strict_fidelity"] = strict_fidelity
        captured["strict_l10n"] = strict_l10n
        captured["strict_a11y"] = strict_a11y
        return screen_ir

    with (
        patch(
            "figma_flutter_agent.generator.ir.passes.apply_ir_layout_passes",
            side_effect=_layout,
        ),
        patch(
            "figma_flutter_agent.generator.ir.passes.apply_ir_classification_passes",
            side_effect=_classify,
        ),
        patch(
            "figma_flutter_agent.generator.ir.passes.fidelity.stamp_fidelity_tiers",
            side_effect=_stamp,
        ),
        patch(
            "figma_flutter_agent.generator.ir.materialize.emit_screen_code_from_ir",
            return_value="class S {}",
        ),
    ):
        materialize_screen_code_from_ir(
            generation,
            clean_tree=clean,
            feature_name="demo",
            ctx=ctx,
            materialize_extracted=False,
        )

    assert captured == {
        "strict_fidelity": True,
        "strict_l10n": True,
        "strict_a11y": True,
    }
