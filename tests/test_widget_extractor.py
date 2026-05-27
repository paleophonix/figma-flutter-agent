from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.widget_extractor import (
    collect_cluster_widget_specs,
    render_cluster_widgets,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_collect_cluster_widget_specs_returns_representatives() -> None:
    cards = [
        CleanDesignTreeNode(
            id=f"{index}:1", name="Product Card", type=NodeType.CARD, cluster_id="cluster_0"
        )
        for index in range(3)
    ]
    root = CleanDesignTreeNode(id="root", name="Screen", type=NodeType.COLUMN, children=cards)

    specs = collect_cluster_widget_specs(root, {"cluster_0": 3})

    assert len(specs) == 1
    assert specs[0].class_name == "ProductCardWidget"
    assert specs[0].file_name == "product_card_widget"


def test_render_cluster_widgets_generates_widget_and_layout_references() -> None:
    cards = [
        CleanDesignTreeNode(
            id=f"{index}:1",
            name="Product Card",
            type=NodeType.CARD,
            cluster_id="cluster_0",
            children=[
                CleanDesignTreeNode(
                    id=f"{index}:text",
                    name="Title",
                    type=NodeType.TEXT,
                    text="Title",
                )
            ],
        )
        for index in range(3)
    ]
    tree = CleanDesignTreeNode(id="root", name="Screen", type=NodeType.COLUMN, children=cards)
    specs = collect_cluster_widget_specs(tree, {"cluster_0": 3})
    result = render_cluster_widgets(specs, uses_svg=False)

    assert "lib/widgets/product_card_widget.dart" in result.files
    assert (
        "class ProductCardWidget extends StatelessWidget"
        in result.files["lib/widgets/product_card_widget.dart"]
    )
    assert (
        "const ProductCardWidget({super.key});"
        in result.files["lib/widgets/product_card_widget.dart"]
    )
    assert result.cluster_classes["cluster_0"] == "ProductCardWidget"

    layout_files = render_layout_file(
        tree,
        feature_name="catalog",
        uses_svg=False,
        cluster_classes=result.cluster_classes,
        widget_imports=["product_card_widget"],
    )
    layout = layout_files["lib/generated/catalog_layout.dart"]

    assert "import 'package:demo_app/widgets/product_card_widget.dart';" in layout
    assert layout.count("const ProductCardWidget()") == 3


def test_render_cluster_widgets_references_nested_cluster_widgets() -> None:
    """Nested cluster children use const shared widgets when all specs are known upfront."""
    title = CleanDesignTreeNode(
        id="1:text",
        name="Title",
        type=NodeType.TEXT,
        text="Title",
        cluster_id="cluster_1",
    )
    cards = [
        CleanDesignTreeNode(
            id=f"{index}:card",
            name="Product Card",
            type=NodeType.CARD,
            cluster_id="cluster_0",
            children=[title],
        )
        for index in range(3)
    ]
    tree = CleanDesignTreeNode(id="root", name="Screen", type=NodeType.COLUMN, children=cards)
    cluster_summary = {"cluster_0": 3, "cluster_1": 3}
    specs = collect_cluster_widget_specs(tree, cluster_summary)
    result = render_cluster_widgets(specs, uses_svg=False)

    card_source = result.files["lib/widgets/product_card_widget.dart"]
    assert "const TitleWidget()" in card_source
    assert "Text('Title'" not in card_source


def test_collect_cluster_widget_specs_respects_min_count() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="1:1", name="Card", type=NodeType.CARD, cluster_id="cluster_0")
        ],
    )
    specs = collect_cluster_widget_specs(root, {"cluster_0": 1}, min_count=2)

    assert specs == []
