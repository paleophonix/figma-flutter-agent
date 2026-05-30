"""Screen IR presence injection for large subtree widgets."""

from __future__ import annotations

from figma_flutter_agent.generator.ir_presence import ensure_presence_subtrees_in_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _vector_subtree(
    node_id: str,
    *,
    width: float,
    height: float,
    top: float,
    count: int = 10,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=width, height=height),
        stack_placement=StackPlacement(left=40.0, top=top, width=width, height=height),
        children=[
            CleanDesignTreeNode(id=f"{node_id}:v", name="Vector", type=NodeType.VECTOR)
            for _ in range(count)
        ],
    )


def test_ensure_presence_injects_missing_subtree_nodes() -> None:
    illustration = _vector_subtree("1:3677", width=332.0, height=243.0, top=160.0)
    logo = _vector_subtree("1:3665", width=168.0, height=30.0, top=6.0, count=10)
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            logo,
            illustration,
            CleanDesignTreeNode(
                id="1:99",
                name="Title",
                type=NodeType.TEXT,
                text="We are what we do",
                stack_placement=StackPlacement(left=58.0, top=534.0, width=300.0, height=42.0),
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:1",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figma_id="1:99", kind=WidgetIrKind.TEXT, children=[]),
            ],
        ),
    )
    patched = ensure_presence_subtrees_in_screen_ir(screen_ir, root, widget_suffix="Widget")
    child_ids = {child.figma_id for child in patched.root.children}
    assert "1:3665" in child_ids
    assert "1:3677" in child_ids
