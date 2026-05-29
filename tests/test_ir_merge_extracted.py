"""Tests for screen IR merge of extracted widget refs."""

from __future__ import annotations

from figma_flutter_agent.generator.ir_emitter import IrEmitContext, emit_merged_root_expression
from figma_flutter_agent.generator.ir_tree import merge_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
)


def test_merge_extracted_replaces_subtree_with_ref_marker() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Inner",
        type=NodeType.TEXT,
        text="hidden",
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Col",
        type=NodeType.COLUMN,
        children=[child],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1",
            kind=WidgetIrKind.AUTO,
            children=[
                WidgetIrNode(
                    figma_id="2",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="BodyBlock"),
                ),
            ],
        ),
    )
    merged = merge_screen_ir(
        root,
        screen_ir,
        extracted_class_by_widget_name={"BodyBlock": "BodyBlock"},
    )
    assert merged.children[0].extracted_widget_ref == "BodyBlock"
    assert merged.children[0].children == []

    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    body = emit_merged_root_expression(merged, ctx=ctx)
    assert "BodyBlock()" in body
    assert "hidden" not in body
