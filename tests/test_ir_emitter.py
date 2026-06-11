"""Phase-0 tests for screen IR merge and Dart emission."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_merged_root_expression
from figma_flutter_agent.generator.ir.screen import emit_screen_code_from_ir
from figma_flutter_agent.generator.ir.tree import default_screen_ir, merge_screen_ir
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    SizingMode,
    WidgetIrKind,
    WidgetIrNode,
)


def test_default_screen_ir_merge_matches_raw_tree_render() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hello",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=100.0),
    )
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=400.0),
        children=[child],
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    ir = default_screen_ir(row)
    merged = merge_screen_ir(row, ir)
    from_ir = emit_merged_root_expression(merged, ctx=ctx)
    from_tree = emit_merged_root_expression(row, ctx=ctx)
    assert from_ir == from_tree


def test_identity_ir_layout_file_contains_flexible_in_row() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hello",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=100.0),
    )
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=400.0),
        children=[child],
    )
    ir = default_screen_ir(row)
    merged = merge_screen_ir(row, ir)
    layout = render_layout_file(merged, feature_name="ir_row", uses_svg=False)[
        "lib/generated/ir_row_layout.dart"
    ]
    assert "Flexible(fit: FlexFit.loose" in layout


def test_validate_rejects_unknown_figma_id() -> None:
    root = CleanDesignTreeNode(id="1", name="Root", type=NodeType.COLUMN, children=[])
    screen_ir = ScreenIr(
        root=WidgetIrNode(figmaId="missing", kind=WidgetIrKind.AUTO, children=[]),
    )
    with pytest.raises(GenerationError, match="not in clean tree"):
        validate_screen_ir(screen_ir, root)


def test_emit_screen_code_balanced_delimiters() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hi",
        sizing=Sizing(width_mode=SizingMode.FILL),
    )
    column = CleanDesignTreeNode(
        id="1",
        name="Column",
        type=NodeType.COLUMN,
        sizing=Sizing(width=320.0, height=480.0),
        children=[child],
    )
    screen_ir = default_screen_ir(column)
    screen_code = emit_screen_code_from_ir(
        screen_ir,
        clean_tree=column,
        screen_class="DemoScreen",
        ctx=IrEmitContext(uses_svg=False, responsive_enabled=False),
        use_scaffold=True,
    )
    assert "class DemoScreen extends StatelessWidget" in screen_code
    assert validate_dart_delimiters(screen_code) is None


def test_ir_reorder_changes_child_order_in_row() -> None:
    first = CleanDesignTreeNode(
        id="2",
        name="A",
        type=NodeType.TEXT,
        text="A",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=40.0),
    )
    second = CleanDesignTreeNode(
        id="3",
        name="B",
        type=NodeType.TEXT,
        text="B",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=40.0),
    )
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=400.0),
        children=[first, second],
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    forward = emit_merged_root_expression(row, ctx=ctx)
    reversed_ir = ScreenIr(
        root=WidgetIrNode(
            figmaId="1",
            kind=WidgetIrKind.AUTO,
            children=[
                WidgetIrNode(figmaId="3", kind=WidgetIrKind.AUTO),
                WidgetIrNode(figmaId="2", kind=WidgetIrKind.AUTO),
            ],
        ),
    )
    reversed_merged = merge_screen_ir(row, reversed_ir)
    backward = emit_merged_root_expression(reversed_merged, ctx=ctx)
    assert forward != backward
    assert forward.index("'A'") < forward.index("'B'")
    assert backward.index("'B'") < backward.index("'A'")
