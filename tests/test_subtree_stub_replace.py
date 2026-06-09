"""Subtree pruning leaves extracted-widget refs in the layout tree."""

from __future__ import annotations

from figma_flutter_agent.generator.subtree import (
    SubtreeWidgetSpec,
    replace_extracted_subtree_nodes_with_refs,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement


def test_replace_extracted_subtree_nodes_with_refs() -> None:
    logo = CleanDesignTreeNode(
        id="1:3665",
        name="Group 17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0),
        stack_placement=StackPlacement(left=123.0, top=6.0, width=168.0, height=30.0),
        children=[
            CleanDesignTreeNode(id="1:3666", name="logo", type=NodeType.STACK, children=[]),
        ],
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        children=[logo],
    )
    specs = (
        SubtreeWidgetSpec(
            node_id="1:3665",
            class_name="Group17Widget",
            file_name="group17_widget",
            representative=logo,
            vector_count=8,
        ),
    )
    replace_extracted_subtree_nodes_with_refs(root, specs)
    assert len(root.children) == 1
    stub = root.children[0]
    assert stub.id == "1:3665"
    assert stub.extracted_widget_ref == "Group17Widget"
    assert stub.children == logo.children
