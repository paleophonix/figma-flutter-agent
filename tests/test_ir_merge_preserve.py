"""IR merge preserves stack visuals without listing every vector in screen IR."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.presence import normalize_screen_ir_presence
from figma_flutter_agent.generator.ir.tree import merge_screen_ir
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
    vectors = [
        _vector(str(index), left=float(index * 4), top=float(index % 20)) for index in range(120)
    ]
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


def test_merge_preserves_column_siblings_omitted_from_partial_ir() -> None:
    headline = CleanDesignTreeNode(
        id="headline",
        name="Headline",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Create account",
            ),
        ],
    )
    form = CleanDesignTreeNode(
        id="form",
        name="Form",
        type=NodeType.INPUT,
        children=[
            CleanDesignTreeNode(
                id="field",
                name="Field",
                type=NodeType.INPUT,
            ),
        ],
    )
    register = CleanDesignTreeNode(
        id="cta",
        name="Register",
        type=NodeType.BUTTON,
        text="Register",
    )
    content = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        children=[headline, form, register],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="content",
            kind=WidgetIrKind.COLUMN,
            children=[
                WidgetIrNode(figma_id="form", kind=WidgetIrKind.INPUT, children=[]),
            ],
        ),
    )
    merged = merge_screen_ir(content, screen_ir)
    child_ids = {child.id for child in merged.children}
    assert child_ids == {"headline", "form", "cta"}


def test_normalize_sync_inserts_missing_column_child_in_ir() -> None:
    headline = CleanDesignTreeNode(
        id="headline",
        name="Headline",
        type=NodeType.TEXT,
        text="Create account",
    )
    register = CleanDesignTreeNode(
        id="cta",
        name="Register",
        type=NodeType.BUTTON,
        text="Register",
    )
    content = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        children=[headline, register],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[content],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="content",
                    kind=WidgetIrKind.AUTO,
                    children=[],
                ),
            ],
        ),
    )
    patched = normalize_screen_ir_presence(screen_ir, root)
    content_ir = next(child for child in patched.root.children if child.figma_id == "content")
    assert {child.figma_id for child in content_ir.children} == {"headline", "cta"}


def test_merge_preserves_component_instance_children_when_ir_empty() -> None:
    icon = CleanDesignTreeNode(
        id="icon",
        name="Icon",
        type=NodeType.VECTOR,
        sizing=Sizing(width=28.0, height=28.0),
        vector_asset_key="assets/icons/category_icon.svg",
    )
    label = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        text="Transfer",
    )
    tile = CleanDesignTreeNode(
        id="tile",
        name="Category tile",
        type=NodeType.STACK,
        component_ref="188:22980",
        sizing=Sizing(width=100.0, height=100.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=100.0, height=100.0),
            ),
            icon,
            label,
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="tile", kind=WidgetIrKind.AUTO, children=[]),
    )
    merged = merge_screen_ir(tile, screen_ir)
    assert {child.id for child in merged.children} == {"surface", "icon", "label"}
