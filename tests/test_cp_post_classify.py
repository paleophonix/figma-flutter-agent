"""Post-classification conservation checkpoint (E2.5-H)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.geometry.invariants.checkpoints import run_cp_post_classify
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from tests.support.semantics_trees import weekday_chip_row


def test_cp_post_classify_passes_after_classify() -> None:
    tree = weekday_chip_row()
    baseline_clean = deep_copy_clean_tree(tree)
    baseline_ir = default_screen_ir(tree)
    updated_ir, _report = classify_screen_ir(baseline_ir.model_copy(deep=True), tree)
    run_cp_post_classify(baseline_clean, baseline_ir, tree, updated_ir)


def test_cp_post_classify_fails_on_clean_tree_mutation() -> None:
    tree = weekday_chip_row()
    baseline_clean = deep_copy_clean_tree(tree)
    baseline_ir = default_screen_ir(tree)
    mutated_clean = deep_copy_clean_tree(tree)
    mutated_clean.children = []
    with pytest.raises(GenerationError, match="CP2_post_classify"):
        run_cp_post_classify(baseline_clean, baseline_ir, mutated_clean, baseline_ir)


def test_cp_post_classify_fails_on_ir_layout_mutation() -> None:
    tree = weekday_chip_row()
    baseline_clean = deep_copy_clean_tree(tree)
    baseline_ir = default_screen_ir(tree)
    mutated_ir = baseline_ir.model_copy(deep=True)
    from figma_flutter_agent.schemas import FlexWrapIr

    mutated_ir.root = mutated_ir.root.model_copy(update={"wrap": FlexWrapIr.EXPANDED})
    with pytest.raises(GenerationError, match="CP2_post_classify"):
        run_cp_post_classify(baseline_clean, baseline_ir, baseline_clean, mutated_ir)
