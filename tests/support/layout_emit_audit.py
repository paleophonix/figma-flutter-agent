"""Emit audit helpers for layout pass acceptance."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def emit_subtree_dart(node: CleanDesignTreeNode) -> str:
    """Render a single clean-tree subtree to Dart widget source."""
    return render_node_body(
        node,
        uses_svg=False,
        is_layout_root=True,
        responsive_enabled=False,
    )


def assert_no_positioned_in_flex_host(node: CleanDesignTreeNode) -> None:
    """Assert de-stacked flex hosts do not emit Positioned wrappers."""
    dart = emit_subtree_dart(node)
    assert "Positioned(" not in dart, dart


def run_passes_and_find_node(
    clean: CleanDesignTreeNode,
    node_id: str,
) -> CleanDesignTreeNode:
    """Apply layout passes and return the updated node by id."""
    screen_ir = default_screen_ir(clean)
    _, updated = apply_ir_layout_passes(screen_ir, clean)
    found = _find_node(updated, node_id)
    if found is None:
        msg = f"node {node_id} missing after layout passes"
        raise AssertionError(msg)
    return found


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def assert_destacked_type(node: CleanDesignTreeNode) -> None:
    """Assert the node was converted from STACK to a flex host."""
    assert node.type in {NodeType.ROW, NodeType.COLUMN, NodeType.WRAP}
