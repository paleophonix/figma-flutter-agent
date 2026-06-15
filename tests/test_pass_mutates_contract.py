"""Pass.mutates contract enforcement."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.contract import validate_pass_mutates
from figma_flutter_agent.generator.ir.passes.protocol import (
    PassContext,
    pass_from_callable,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr


def test_validate_pass_mutates_flags_undeclared_style_change() -> None:
    before = CleanDesignTreeNode(
        id="root",
        name="Root",
        type="CONTAINER",
        style={"font_size": 14.0},
        children=[],
    )
    after = CleanDesignTreeNode(
        id="root",
        name="Root",
        type="CONTAINER",
        style={"font_size": 18.0},
        children=[],
    )
    screen_ir = ScreenIr.model_validate(
        {
            "root": {
                "figmaId": "root",
                "kind": "container",
                "children": [],
            },
        },
    )

    def _noop(ctx: PassContext) -> PassContext:
        return ctx

    registered = pass_from_callable(
        "noop",
        _noop,
        mutates=frozenset({"children"}),
        preserves=frozenset(),
    )
    violations = validate_pass_mutates(
        registered,
        before_clean=before,
        after_clean=after,
        before_ir=screen_ir,
        after_ir=screen_ir,
    )
    assert violations
    assert violations[0].code == "pass_over_mutation"


def test_validate_pass_mutates_flags_structural_children_change() -> None:
    before = CleanDesignTreeNode(
        id="root",
        name="Root",
        type="CONTAINER",
        children=[
            CleanDesignTreeNode(id="a", name="a", type="TEXT", text="a"),
        ],
    )
    after = CleanDesignTreeNode(
        id="root",
        name="Root",
        type="CONTAINER",
        children=[
            CleanDesignTreeNode(id="b", name="b", type="TEXT", text="b"),
        ],
    )
    screen_ir = ScreenIr.model_validate(
        {
            "root": {
                "figmaId": "root",
                "kind": "container",
                "children": [],
            },
        },
    )

    def _noop(ctx: PassContext) -> PassContext:
        return ctx

    registered = pass_from_callable(
        "noop",
        _noop,
        mutates=frozenset({"type"}),
        preserves=frozenset(),
    )
    violations = validate_pass_mutates(
        registered,
        before_clean=before,
        after_clean=after,
        before_ir=screen_ir,
        after_ir=screen_ir,
    )
    assert violations
    assert any(v.detail and "children" in v.detail for v in violations)


def test_unstack_mutates_child_placement_without_parent_children_violation() -> None:
    from figma_flutter_agent.generator.ir.passes.registry import WAVE_1_IR_PASSES
    from figma_flutter_agent.generator.ir.passes.unstack import unstack_homogeneous_stack
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from tests.test_ir_layout_passes import _horizontal_chip_stack

    chip = _horizontal_chip_stack()
    chip_ir = default_screen_ir(chip)
    after_ir, after_clean = unstack_homogeneous_stack(chip_ir, chip)
    registered = next(p for p in WAVE_1_IR_PASSES if p.name == "unstack")
    violations = validate_pass_mutates(
        registered,
        before_clean=chip,
        after_clean=after_clean,
        before_ir=chip_ir,
        after_ir=after_ir,
    )
    assert violations == []
