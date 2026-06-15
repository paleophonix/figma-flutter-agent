"""Unit tests for screen IR LLM-drift sanitizers."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.presence.sanitize import (
    sanitize_screen_ir_duplicate_figma_ids,
    sanitize_screen_ir_extracted_refs,
    sanitize_screen_ir_llm_drift,
    sanitize_screen_ir_phantom_nodes,
    sanitize_screen_ir_state_by_figma_id,
)
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
    WidgetIrState,
)


def test_sanitize_state_prunes_unknown_figma_ids() -> None:
    root = CleanDesignTreeNode(id="1:0", name="Screen", type=NodeType.STACK)
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="1:0"),
        state_by_figma_id={"9:9": WidgetIrState.DISABLED},
    )
    pruned = sanitize_screen_ir_state_by_figma_id(screen_ir, root)
    assert pruned == 1
    assert screen_ir.state_by_figma_id == {}


def test_sanitize_phantom_nodes_prunes_unknown_subtree() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(id="1:1", name="Btn", type=NodeType.BUTTON),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:0",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figma_id="1:1", kind=WidgetIrKind.BUTTON),
                WidgetIrNode(figma_id="9:9", kind=WidgetIrKind.TEXT),
            ],
        ),
    )
    pruned = sanitize_screen_ir_phantom_nodes(screen_ir, root)
    assert pruned == 1
    assert {c.figma_id for c in screen_ir.root.children} == {"1:1"}


def test_sanitize_duplicate_figma_ids_keeps_first() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        children=[CleanDesignTreeNode(id="dup", name="A", type=NodeType.TEXT, text="a")],
    )
    dup = WidgetIrNode(figma_id="dup", kind=WidgetIrKind.TEXT)
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.COLUMN,
            children=[dup, dup.model_copy(deep=True)],
        ),
    )
    dropped = sanitize_screen_ir_duplicate_figma_ids(screen_ir)
    assert dropped == 1
    assert len(screen_ir.root.children) == 1
    validate_screen_ir(screen_ir, root, apply_guards=False)


def test_sanitize_extracted_strips_children_and_downgrades_empty_ref() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(id="1:1", name="Card", type=NodeType.STACK),
            CleanDesignTreeNode(id="1:2", name="Btn", type=NodeType.BUTTON),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:0",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="1:1",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="CardWidget"),
                    children=[WidgetIrNode(figma_id="1:9", kind=WidgetIrKind.TEXT)],
                ),
                WidgetIrNode(
                    figma_id="1:2",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name=""),
                ),
            ],
        ),
    )
    downgraded, stripped = sanitize_screen_ir_extracted_refs(
        screen_ir,
        root,
        extracted_widget_names=frozenset({"CardWidget"}),
    )
    assert stripped == 1
    assert downgraded == 1
    assert screen_ir.root.children[0].children == []
    assert screen_ir.root.children[1].kind == WidgetIrKind.BUTTON


def test_sanitize_extracted_input_downgrades_even_when_declared_widget() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:1",
                name="Email",
                type=NodeType.INPUT,
                children=[
                    CleanDesignTreeNode(
                        id="1:2",
                        name="Surface",
                        type=NodeType.CONTAINER,
                        sizing=Sizing(width=327.0, height=46.0),
                        style=NodeStyle(background_color="0xFFFFFFFF"),
                    )
                ],
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:0",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="1:1",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="InputFieldWidget"),
                ),
            ],
        ),
    )
    downgraded, stripped = sanitize_screen_ir_extracted_refs(
        screen_ir,
        root,
        extracted_widget_names=frozenset({"InputFieldWidget"}),
    )
    assert downgraded == 1
    assert stripped == 0
    assert screen_ir.root.children[0].kind == WidgetIrKind.INPUT


def test_validate_sanitizes_omit_on_real_child() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(id="1:1", name="Label", type=NodeType.TEXT, text="Hi"),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:0",
            kind=WidgetIrKind.STACK,
            children=[WidgetIrNode(figma_id="1:1", kind=WidgetIrKind.TEXT)],
        ),
        omit_figma_ids=["1:1"],
    )
    validate_screen_ir(screen_ir, root, apply_guards=False)
    assert "1:1" not in screen_ir.omit_figma_ids


def test_llm_drift_orchestrator_runs_without_error() -> None:
    root = CleanDesignTreeNode(id="1:0", name="Screen", type=NodeType.STACK)
    screen_ir = ScreenIr(root=WidgetIrNode(figma_id="1:0"))
    summary = sanitize_screen_ir_llm_drift(
        screen_ir,
        root,
        declared_extracted_widget_names=frozenset(),
    )
    assert summary.omit_ids_removed == 0
