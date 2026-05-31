"""IR merge preserves stack visuals without listing every vector in screen IR."""

from __future__ import annotations

from figma_flutter_agent.generator.ir_presence import normalize_screen_ir_presence
from figma_flutter_agent.generator.ir_tree import merge_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _vector(id_suffix: str, *, left: float, top: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=f"v:{id_suffix}",
        name="Vector",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=left, top=top, width=12.0, height=12.0),
    )


def test_merge_preserves_many_vectors_without_ir_entries() -> None:
    vectors = [_vector(str(index), left=float(index * 14), top=10.0) for index in range(80)]
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=vectors,
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="root", kind=WidgetIrKind.STACK, children=[]),
    )
    merged = merge_screen_ir(root, screen_ir)
    assert len(merged.children) == 80


def test_normalize_keeps_ir_graph_small_on_vector_heavy_screen() -> None:
    vectors = [_vector(str(index), left=float(index * 4), top=float(index % 20)) for index in range(120)]
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=vectors,
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figma_id="v:0", kind=WidgetIrKind.AUTO, children=[]),
            ],
        ),
    )

    def count_ir_nodes(node: WidgetIrNode) -> int:
        total = 1
        for child in node.children:
            total += count_ir_nodes(child)
        return total

    patched = normalize_screen_ir_presence(screen_ir, root)
    assert count_ir_nodes(patched.root) < 80
