"""Placement geometry conservation (Track B / B4)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    capture_placement_baseline,
    check_placement_truth_preserved,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement


def test_placement_baseline_detects_stack_top_drift() -> None:
    node = CleanDesignTreeNode(
        id="1:nav",
        name="Nav",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=80.0),
        stack_placement=StackPlacement(vertical="BOTTOM", top=760.0, height=80.0),
        children=[],
    )
    baseline = capture_placement_baseline(node)
    placement = node.stack_placement
    assert placement is not None
    mutated = node.model_copy(
        update={
            "stack_placement": placement.model_copy(update={"top": 738.0}),
        },
        deep=True,
    )
    violations = check_placement_truth_preserved(baseline, mutated)
    assert violations
    assert violations[0].code == "inv_geometry_truth"
