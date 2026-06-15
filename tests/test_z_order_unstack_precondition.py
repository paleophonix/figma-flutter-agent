"""Z-order contract guard for unstacking passes (E0.3 / E4 precondition)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _chip_stack() -> CleanDesignTreeNode:
    children = [
        CleanDesignTreeNode(
            id=f"chip:{index}",
            name=f"Chip {index}",
            type=NodeType.TEXT,
            text=str(index),
            stack_placement=StackPlacement(
                left=10.0 + index * 70.0,
                top=4.0,
                width=60.0,
                height=24.0,
            ),
        )
        for index in range(3)
    ]
    return CleanDesignTreeNode(
        id="stack:1",
        name="ChipRow",
        type=NodeType.STACK,
        sizing=Sizing(width=240.0, height=32.0),
        children=children,
    )


def test_unstacking_preserves_clean_tree_child_order() -> None:
    clean_tree = _chip_stack()
    paint_order_before = [child.id for child in clean_tree.children]
    screen_ir = default_screen_ir(clean_tree)
    updated_ir, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean_tree,
        macro_height_threshold_px=900,
    )
    assert updated_ir is not None
    paint_order_after = [child.id for child in updated_clean.children]
    assert paint_order_after == paint_order_before


def test_stack_child_order_reorder_does_not_change_merge_order() -> None:
    from figma_flutter_agent.generator.ir.tree import merge_screen_ir
    from tests.support.conservation import assert_stack_z_order_preserved

    clean_tree = _chip_stack()
    reversed_order = list(reversed([child.id for child in clean_tree.children]))
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="stack:1",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figma_id=child.id, kind=WidgetIrKind.AUTO)
                for child in reversed(clean_tree.children)
            ],
        ),
        stack_child_order=reversed_order,
    )
    merged = merge_screen_ir(clean_tree, screen_ir)
    assert [child.id for child in merged.children] == [child.id for child in clean_tree.children]
    assert_stack_z_order_preserved(clean_tree, merged)


def test_stack_child_order_with_pruned_duplicate_instances() -> None:
    from figma_flutter_agent.generator.ir.tree import merge_screen_ir
    from figma_flutter_agent.parser.dedup.clusters import assign_structural_clusters
    from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree
    from tests.support.conservation import (
        assert_node_multiset_preserved,
        assert_stack_z_order_preserved,
    )

    children = [
        CleanDesignTreeNode(
            id=f"icon:{index}",
            name="Icon",
            type=NodeType.STACK,
            stack_placement=StackPlacement(
                left=10.0 + index * 30.0,
                top=4.0,
                width=24.0,
                height=24.0,
            ),
            children=[
                CleanDesignTreeNode(
                    id=f"icon:{index}:vector",
                    name="Vector",
                    type=NodeType.VECTOR,
                    sizing=Sizing(width=20.0, height=20.0),
                )
            ],
        )
        for index in range(4)
    ]
    clean_tree = CleanDesignTreeNode(
        id="stack:icons",
        name="IconRow",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=40.0),
        children=children,
    )
    assign_structural_clusters(clean_tree)
    prune_generation_layout_tree(clean_tree)
    assert len(clean_tree.children) == 4

    screen_ir = default_screen_ir(clean_tree)
    assert_node_multiset_preserved(clean_tree, screen_ir)
    merged = merge_screen_ir(
        clean_tree,
        ScreenIr(
            root=screen_ir.root,
            stack_child_order=list(reversed([child.id for child in clean_tree.children])),
        ),
    )
    assert_stack_z_order_preserved(clean_tree, merged)
    assert [child.id for child in merged.children] == [child.id for child in clean_tree.children]
