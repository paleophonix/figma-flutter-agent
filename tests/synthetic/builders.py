"""Deterministic synthetic clean-tree builders (Program 08 P0-1)."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def column_tree(*, depth: int = 1, width: float = 360.0, height: float = 640.0) -> CleanDesignTreeNode:
    """Build a shallow column tree with deterministic ids."""
    children: list[CleanDesignTreeNode] = []
    for index in range(max(1, depth)):
        children.append(
            CleanDesignTreeNode(
                id=f"leaf-{index}",
                name=f"Leaf {index}",
                type=NodeType.TEXT,
                text=f"text-{index}",
            ),
        )
    return CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=width, height=height),
        children=children,
    )


def stack_pair(*, gap: float = 8.0) -> CleanDesignTreeNode:
    """Two stacked frames for layout metamorphic tests."""
    return CleanDesignTreeNode(
        id="stack-root",
        name="Stack",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=200.0),
        children=[
            CleanDesignTreeNode(
                id="a",
                name="A",
                type=NodeType.VECTOR,
                sizing=Sizing(width=100.0, height=40.0),
            ),
            CleanDesignTreeNode(
                id="b",
                name="B",
                type=NodeType.VECTOR,
                sizing=Sizing(width=100.0, height=40.0),
            ),
        ],
    )
