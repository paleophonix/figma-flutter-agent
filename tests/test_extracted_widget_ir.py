"""Tests for extracted widget IR materialization."""

from __future__ import annotations

import pytest

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.extracted import emit_extracted_widget_code_from_ir
from figma_flutter_agent.generator.ir.materialize import materialize_screen_code_from_ir
from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ExtractedWidget,
    FlutterGenerationResponse,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
)


def test_extracted_widget_requires_code_or_ir() -> None:
    with pytest.raises(ValueError, match="widgetIr or code"):
        ExtractedWidget(widget_name="Foo")


def test_emit_extracted_widget_from_ir() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hi",
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Card",
        type=NodeType.COLUMN,
        children=[child],
    )
    widget_ir = WidgetIrNode(
        figma_id="1",
        kind=WidgetIrKind.AUTO,
        children=[WidgetIrNode(figma_id="2", kind=WidgetIrKind.AUTO)],
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    code = emit_extracted_widget_code_from_ir(
        widget_ir,
        clean_tree=root,
        widget_name="card_widget",
        ctx=ctx,
    )
    assert "class CardWidget extends StatelessWidget" in code
    assert "'Hi'" in code


def test_empty_widget_ir_emits_full_clean_subtree() -> None:
    """Empty widgetIr children must not collapse a multi-child clean subtree to one asset."""
    children = [
        CleanDesignTreeNode(
            id=f"chip-{index}",
            name=f"Chip {index}",
            type=NodeType.TEXT,
            text=f"Label {index}",
            stack_placement=StackPlacement(left=float(index * 70), top=0.0, width=60.0, height=32.0),
        )
        for index in range(3)
    ]
    root = CleanDesignTreeNode(
        id="row",
        name="CategoryRow",
        type=NodeType.STACK,
        sizing=Sizing(width=300.0, height=92.0),
        children=children,
    )
    widget_ir = WidgetIrNode(figma_id="row", kind=WidgetIrKind.AUTO, children=[])
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    code = emit_extracted_widget_code_from_ir(
        widget_ir,
        clean_tree=root,
        widget_name="category_row_widget",
        ctx=ctx,
    )
    assert "Label 0" in code
    assert "Label 1" in code
    assert "Label 2" in code


def test_screen_ir_extracted_ref_emits_widget_call() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Yo",
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[child],
    )
    widget_ir = WidgetIrNode(figma_id="2", kind=WidgetIrKind.AUTO)
    generation = FlutterGenerationResponse(
        screen_ir=ScreenIr(
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
        ),
        extracted_widgets=[
            ExtractedWidget(widget_name="BodyBlock", widget_ir=widget_ir),
        ],
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    out = materialize_screen_code_from_ir(
        generation,
        clean_tree=root,
        feature_name="demo",
        ctx=ctx,
    )
    assert "BodyBlock()" in out.screen_code
    assert "'Yo'" not in out.screen_code


def test_materialize_generation_compiles_extracted_widgets() -> None:
    from figma_flutter_agent.generator.ir.tree import default_screen_ir

    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Yo",
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[child],
    )
    widget_ir = WidgetIrNode(figma_id="2", kind=WidgetIrKind.AUTO)
    generation = FlutterGenerationResponse(
        screen_ir=default_screen_ir(root),
        extracted_widgets=[
            ExtractedWidget(widget_name="BodyBlock", widget_ir=widget_ir),
        ],
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    out = materialize_screen_code_from_ir(
        generation,
        clean_tree=root,
        feature_name="demo",
        ctx=ctx,
    )
    assert out.extracted_widgets[0].resolved_code()
    assert "extends StatelessWidget" in out.extracted_widgets[0].resolved_code()
    assert out.resolved_screen_code()
    assert "'Yo'" in out.screen_code


def test_materialize_screen_ir_overrides_legacy_screen_code() -> None:
    from figma_flutter_agent.generator.ir.tree import default_screen_ir

    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="From IR",
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[child],
    )
    generation = FlutterGenerationResponse(
        screen_ir=default_screen_ir(root),
        screen_code=(
            "class DemoScreen extends StatelessWidget {\n"
            "  const DemoScreen({super.key});\n"
            "  @override\n"
            "  Widget build(BuildContext context) => const Text('LLM_STUB_MARKER');\n"
            "}\n"
            "class GroupWidget extends StatelessWidget {\n"
            "  const GroupWidget({super.key});\n"
            "  @override\n"
            "  Widget build(BuildContext context) => const SizedBox.shrink();\n"
            "}\n"
        ),
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    out = materialize_screen_code_from_ir(
        generation,
        clean_tree=root,
        feature_name="demo",
        ctx=ctx,
    )
    assert "LLM_STUB_MARKER" not in out.screen_code
    assert "class GroupWidget extends" not in out.screen_code
    assert "From IR" in out.screen_code


def test_materialize_skips_widget_ir_when_subtree_pruned_from_clean_tree() -> None:
    """true_subtree_pruning removes widget roots before IR emit; must not hard-fail plan."""
    logo = CleanDesignTreeNode(
        id="1:3665",
        name="Group17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0),
        stack_placement=StackPlacement(left=123.0, top=6.0, width=168.0, height=30.0),
        children=[CleanDesignTreeNode(id="1:1", name="Vector", type=NodeType.VECTOR)],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[logo],
    )
    prune_generation_layout_tree(root, extracted_subtree_node_ids=frozenset({"1:3665"}))
    stub = (
        "class Group17Widget extends StatelessWidget { "
        "const Group17Widget({super.key}); "
        "@override Widget build(BuildContext c) => const SizedBox.shrink(); }"
    )
    generation = FlutterGenerationResponse(
        screen_ir=ScreenIr(
            root=WidgetIrNode(figma_id="root", kind=WidgetIrKind.STACK, children=[]),
        ),
        extracted_widgets=[
            ExtractedWidget(
                widget_name="Group17Widget",
                code=stub,
                widget_ir=WidgetIrNode(figma_id="1:3665", kind=WidgetIrKind.STACK),
            ),
        ],
    )
    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    out = materialize_screen_code_from_ir(
        generation,
        clean_tree=root,
        feature_name="sign_up_and_sign_in",
        ctx=ctx,
        prefer_existing_extracted_code=False,
    )
    assert out.extracted_widgets[0].resolved_code() == stub
