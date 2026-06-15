"""Per-pass preservation contract tests."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_ir_kind_preserved,
)
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


def _simple_column() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing={"width": 360.0, "height": 800.0},
        children=[
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Hello",
                sizing={"width": 200.0, "height": 24.0},
            ),
        ],
    )


def test_layout_passes_satisfy_per_pass_contracts() -> None:
    tree = _simple_column()
    screen_ir = default_screen_ir(tree)
    apply_ir_layout_passes(screen_ir, tree, inject_root_scroll_host=True, validate_cp2=True)


def test_check_ir_kind_preserved_detects_drift() -> None:
    baseline = ScreenIr(
        root=WidgetIrNode(figma_id="root", kind=WidgetIrKind.COLUMN, children=[]),
    )
    current = ScreenIr(
        root=WidgetIrNode(figma_id="root", kind=WidgetIrKind.ROW, children=[]),
    )
    violations = check_ir_kind_preserved(baseline, current)
    assert violations
    assert violations[0].code == "inv_ir_kind"
    assert violations[0].node_id == "root"


def test_check_ir_kind_preserved_accepts_unchanged() -> None:
    baseline = ScreenIr(
        root=WidgetIrNode(figma_id="root", kind=WidgetIrKind.COLUMN, children=[]),
    )
    current = baseline.model_copy(deep=True)
    assert check_ir_kind_preserved(baseline, current) == []
