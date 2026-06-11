"""Conservation checks for de-stacked flex hosts."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_flex_hosts_have_no_stack_placement,
)
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_destacked_row_clears_child_stack_placement() -> None:
    clean = CleanDesignTreeNode(
        id="host",
        name="chips",
        type=NodeType.STACK,
        sizing=Sizing(width=400.0, height=40.0),
        children=[
            CleanDesignTreeNode(
                id="a",
                name="a",
                type=NodeType.TEXT,
                text="a",
                stack_placement=StackPlacement(left=0.0, top=0.0, width=60.0, height=32.0),
            ),
            CleanDesignTreeNode(
                id="b",
                name="b",
                type=NodeType.TEXT,
                text="b",
                stack_placement=StackPlacement(left=68.0, top=0.0, width=60.0, height=32.0),
            ),
        ],
    )
    screen_ir = default_screen_ir(clean)
    _, updated = apply_ir_layout_passes(screen_ir, clean, validate_cp2=False)
    assert check_flex_hosts_have_no_stack_placement(updated) == []
