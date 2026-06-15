"""Pass.mutates contract enforcement."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.contract import validate_pass_mutates
from figma_flutter_agent.generator.ir.passes.protocol import Pass, PassContext, pass_from_callable
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
