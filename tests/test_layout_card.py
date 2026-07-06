"""Layout rendering tests for semantic node types."""

from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


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


def test_horizontal_product_row_card_emits_row_not_column() -> None:
    node = CleanDesignTreeNode(
        id="card",
        name="Card",
        type=NodeType.CARD,
        spacing=12.0,
        sizing=Sizing(width=347.0, height=76.0, width_mode=SizingMode.FILL),
        children=[
            CleanDesignTreeNode(
                id="img",
                name="Img",
                type=NodeType.IMAGE,
                sizing=Sizing(
                    width=76.0,
                    height=76.0,
                    width_mode=SizingMode.FIXED,
                    height_mode=SizingMode.FIXED,
                ),
                image_asset_key="assets/images/sushi.png",
            ),
            CleanDesignTreeNode(
                id="body",
                name="Body",
                type=NodeType.COLUMN,
                sizing=Sizing(width=259.0, height=72.0, width_mode=SizingMode.FILL),
                children=[
                    CleanDesignTreeNode(
                        id="title",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Okinawa",
                    ),
                ],
            ),
        ],
    )

    body = render_node_body(node, uses_svg=False)

    assert "Row(" in body
    assert "Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [Image.asset" not in body
