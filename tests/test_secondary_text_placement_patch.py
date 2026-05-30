"""Secondary TEXT placement below opaque fills (geometry-only)."""

from __future__ import annotations

from figma_flutter_agent.generator.llm_dart import _patch_secondary_text_below_opaque_fill
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, StackPlacement


def test_patch_moves_lower_text_below_fill_without_label_matching() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Footer",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Fill",
                type=NodeType.CONTAINER,
                style=NodeStyle(background_color="0xFF112233"),
                stack_placement=StackPlacement(left=0, top=0, width=100, height=40),
            ),
            CleanDesignTreeNode(
                id="1:3",
                name="Primary",
                type=NodeType.TEXT,
                text="Continue",
                stack_placement=StackPlacement(left=10, top=5, width=50, height=12),
            ),
            CleanDesignTreeNode(
                id="1:4",
                name="Secondary",
                type=NodeType.TEXT,
                text="Maybe later",
                stack_placement=StackPlacement(left=10, top=25, width=80, height=12),
            ),
        ],
    )
    screen = """
    Stack(
      children: [
        Positioned(
          key: ValueKey('figma-1_4'),
          left: 10.0,
          top: 25.0,
          child: Text('Maybe later'),
        ),
      ],
    );
    """
    patched = _patch_secondary_text_below_opaque_fill(screen, root)
    assert "top: 44.0" in patched
