"""Provenance recording tests for layout passes."""

from __future__ import annotations

from figma_flutter_agent.debug.provenance import ProvenanceRecorder
from figma_flutter_agent.generator.ir.passes.manager import PassManager
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)


def _chip_row() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="host",
        name="chips",
        type=NodeType.STACK,
        sizing=Sizing(width=400.0, height=40.0),
        children=[
            CleanDesignTreeNode(
                id=f"c{index}",
                name=f"c{index}",
                type=NodeType.TEXT,
                text=str(index),
                sizing=Sizing(width=60.0, height=32.0),
                stack_placement=StackPlacement(
                    left=float(index * 68),
                    top=0.0,
                    width=60.0,
                    height=32.0,
                ),
            )
            for index in range(3)
        ],
    )


def test_unstack_records_field_mutations(monkeypatch) -> None:
    recorder = ProvenanceRecorder(feature_name="layout_pass_test")
    monkeypatch.setattr(
        "figma_flutter_agent.debug.provenance.get_provenance_recorder",
        lambda: recorder,
    )
    clean = _chip_row()
    screen_ir = default_screen_ir(clean)
    PassManager().run(screen_ir, clean, validate_cp2=False)
    transforms = {entry.transform for entry in recorder.mutations}
    assert "unstack" in transforms
    type_mutations = [entry for entry in recorder.mutations if entry.field == "type"]
    assert type_mutations
    assert type_mutations[0].old == NodeType.STACK.value
