"""INV-2: guard passes must not mutate the input clean tree."""

from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import apply_ir_guards, validate_screen_ir
from figma_flutter_agent.generator.tree_copy import hash_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement


def _minimal_root() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="btn",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width=200.0, height=48.0),
            )
        ],
    )


def test_apply_ir_guards_does_not_mutate_original_clean_tree() -> None:
    root = _minimal_root()
    before = hash_clean_tree(root)
    screen_ir = default_screen_ir(root)
    normalized = apply_ir_guards(screen_ir, root)
    after = hash_clean_tree(root)
    assert before == after
    assert normalized is not root

