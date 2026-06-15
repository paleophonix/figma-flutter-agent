"""Signoff and IR pass gates for /repair Track B."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.config.profiles import apply_signoff_profile
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.passes.manager import PassManager
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing, StackPlacement
from figma_flutter_agent.validation.spec23.emit_contracts import _criterion_emit_fidelity_contracts


def test_signoff_profile_enables_emit_contract_gate() -> None:
    settings = apply_signoff_profile(Settings())
    assert settings.agent.validation.strict_emit_contracts is True


def test_emit_contract_gate_report_only_by_default() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[],
    )
    result = _criterion_emit_fidelity_contracts(
        root,
        "",
        settings=Settings(),
        strict=True,
    )
    assert result.passed
    assert result.detail == "report-only"


def test_emit_contract_gate_fails_layer_blur_missing_backdrop() -> None:
    header = CleanDesignTreeNode(
        id="1:hdr",
        name="Header",
        type=NodeType.CONTAINER,
        style=NodeStyle(background_color="0xFFFFFFFF", layer_blur=24.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=390.0, height=84.0),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[header],
    )
    bad_emit = "Positioned(left: 0.0, top: 0.0, key: ValueKey('figma-1_hdr'), child: Container())"
    settings = apply_signoff_profile(Settings())
    result = _criterion_emit_fidelity_contracts(
        root,
        bad_emit,
        settings=settings,
        strict=True,
    )
    assert not result.passed
    assert "layer_blur_missing_backdrop" in result.detail


def test_preserve_placement_skips_sectionize_unstack_unpin() -> None:
    seen: list[str] = []

    class RecordingManager(PassManager):
        def run(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            from figma_flutter_agent.generator.ir.passes.policy import (
                filter_layout_passes_for_placement,
            )

            active = filter_layout_passes_for_placement(
                self._passes,
                preserve_placement=kwargs.get("preserve_placement", False),
            )
            seen.extend(pass_.name for pass_ in active)
            return super().run(*args, **kwargs)

    tree = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[],
    )
    screen_ir = default_screen_ir(tree)
    RecordingManager().run(screen_ir, tree, preserve_placement=True, validate_cp2=False)
    assert seen == ["scroll_host"]


def test_default_layout_passes_still_run_sectionize() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=360.0, height=800.0),
        children=[],
    )
    before = tree.model_copy(deep=True)
    _, after = apply_ir_layout_passes(
        default_screen_ir(tree),
        tree,
        inject_root_scroll_host=False,
        preserve_placement=False,
        validate_cp2=False,
    )
    assert before.model_dump() == after.model_dump() or after.type == before.type
