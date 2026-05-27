"""Tests for optional spec §9 UX hard gates."""

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.parser.ux import enforce_ux_gates
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _deep_tree(depth: int) -> CleanDesignTreeNode:
    node = CleanDesignTreeNode(id="leaf", name="Leaf", type=NodeType.TEXT, text="x")
    for index in range(depth - 1):
        node = CleanDesignTreeNode(
            id=f"n{index}",
            name=f"Level{index}",
            type=NodeType.COLUMN,
            children=[node],
        )
    return node


def test_enforce_ux_gates_raises_on_deep_tree() -> None:
    try:
        enforce_ux_gates(_deep_tree(10), max_layout_depth=8)
    except GenerationError as exc:
        assert "exceeds limit" in str(exc)
    else:
        raise AssertionError("expected GenerationError")
