"""Layout rendering tests for semantic node types."""

from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_render_node_body_emits_card_widget() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Product Card",
        type=NodeType.CARD,
        children=[
            CleanDesignTreeNode(id="2", name="Title", type=NodeType.TEXT, text="Hello"),
        ],
    )

    body = render_node_body(node, uses_svg=False)

    assert "Card(" in body
    assert "Text('Hello'" in body
