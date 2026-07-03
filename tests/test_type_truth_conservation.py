"""LAW-CP1-TYPE-TRUTH closure via conservation registry (Program 08 P0-0)."""

from __future__ import annotations

import copy

from figma_flutter_agent.generator.geometry.invariants.conservation import check_type_truth
from figma_flutter_agent.generator.geometry.invariants.models import GeometryInvariantViolation
from figma_flutter_agent.generator.geometry.invariants.registry import (
    ConservationLawContext,
    execute_conservation_laws,
    law_by_id,
)
from figma_flutter_agent.generator.geometry.invariants.type_truth import capture_type_baseline
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _tree(*, node_type: NodeType = NodeType.COLUMN) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="root",
        type=node_type,
        children=[
            CleanDesignTreeNode(id="leaf", name="leaf", type=NodeType.TEXT),
        ],
    )


def _run_type_truth_law(ctx: ConservationLawContext) -> list[GeometryInvariantViolation]:
    law = law_by_id("LAW-CP1-TYPE-TRUTH")
    assert law is not None
    assert hasattr(law, "check_fn")
    return list(law.check_fn(ctx))  # type: ignore[union-attr]


def test_type_truth_pass_when_types_unchanged() -> None:
    tree = _tree()
    baseline = capture_type_baseline(tree)
    ctx = ConservationLawContext(
        baseline_clean=tree,
        current_clean=tree,
        type_baseline=baseline,
    )
    assert _run_type_truth_law(ctx) == []
    assert execute_conservation_laws("CP1", ctx) == []


def test_type_truth_violation_without_permit() -> None:
    tree = _tree()
    mutated = copy.deepcopy(tree)
    mutated.children[0].type = NodeType.BUTTON
    baseline = capture_type_baseline(tree)
    violations = check_type_truth(baseline, mutated)
    assert len(violations) == 1
    assert violations[0].code == "inv_type_truth"
    assert violations[0].node_id == "leaf"


def test_type_truth_permit_allows_legacy_policy() -> None:
    tree = _tree()
    mutated = copy.deepcopy(tree)
    mutated.children[0].type = NodeType.BUTTON
    baseline = capture_type_baseline(tree)
    allowed = {("leaf", "type"): "legacy_semantic_type"}
    assert check_type_truth(baseline, mutated, allowed_mutations=allowed) == []


def test_type_truth_permit_wrong_node_still_violates() -> None:
    tree = _tree()
    mutated = copy.deepcopy(tree)
    mutated.children[0].type = NodeType.BUTTON
    baseline = capture_type_baseline(tree)
    allowed = {("other-id", "type"): "legacy_semantic_type"}
    assert check_type_truth(baseline, mutated, allowed_mutations=allowed)


def test_type_truth_permit_wrong_field_pair_still_violates() -> None:
    tree = _tree()
    mutated = copy.deepcopy(tree)
    mutated.children[0].type = NodeType.BUTTON
    baseline = capture_type_baseline(tree)
    allowed = {("leaf", "name"): "legacy_semantic_type"}
    assert check_type_truth(baseline, mutated, allowed_mutations=allowed)


def test_type_truth_delete_recreate_mask_not_in_baseline() -> None:
    """Deleted node id absent from baseline does not mask a sibling type drift."""
    tree = _tree()
    baseline = capture_type_baseline(tree)
    # simulate delete/recreate: new id, old id gone
    replaced = CleanDesignTreeNode(
        id="root",
        name="root",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="leaf-new", name="leaf", type=NodeType.BUTTON),
        ],
    )
    violations = check_type_truth(baseline, replaced)
    assert violations == []


def test_type_truth_empty_baseline_unavailable_not_silent_pass() -> None:
    tree = _tree()
    mutated = copy.deepcopy(tree)
    mutated.children[0].type = NodeType.BUTTON
    ctx = ConservationLawContext(
        baseline_clean=tree,
        current_clean=mutated,
        type_baseline=None,
    )
    registry_result = _run_type_truth_law(ctx)
    direct = check_type_truth({}, mutated)
    assert registry_result == []
    assert len(direct) == 0
    assert ctx.type_baseline is None
