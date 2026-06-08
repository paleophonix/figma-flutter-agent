"""Pipeline must leave extracted-widget stubs in the clean tree for layout/IR."""

from __future__ import annotations

from figma_flutter_agent.generator.subtree_widgets import (
    collect_subtree_widget_specs,
    replace_extracted_subtree_nodes_with_refs,
)
from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement


def _vector_leaf(node_id: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(id=node_id, name="Vector", type=NodeType.VECTOR)


def test_pipeline_subtree_prune_leaves_placement_stubs() -> None:
    vectors = [_vector_leaf(f"1:{3700 + i}") for i in range(10)]
    logo = CleanDesignTreeNode(
        id="1:3665",
        name="Group 17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0),
        stack_placement=StackPlacement(left=123.0, top=6.0, width=168.0, height=30.0),
        children=vectors,
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[logo],
    )
    specs = collect_subtree_widget_specs(root, widget_suffix="Widget")
    assert any(spec.node_id == "1:3665" for spec in specs)
    replace_extracted_subtree_nodes_with_refs(root, specs)
    prune_generation_layout_tree(root, extracted_subtree_node_ids=frozenset())
    assert [child.id for child in root.children] == ["1:3665"]
    assert root.children[0].extracted_widget_ref
    assert len(root.children[0].children) == len(vectors)
