"""Widget annotation marker parsing tests."""

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.widget_extraction import collect_widget_specs
from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets
from figma_flutter_agent.parser.annotations.widget_marker import (
    parse_widget_annotation,
    resolve_widget_class_name,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_parse_widget_annotation_case_insensitive() -> None:
    parsed = parse_widget_annotation("@Widget:PrimaryButton")
    assert parsed is not None
    assert parsed.requested_name == "PrimaryButton"


def test_resolve_widget_class_name_from_layer() -> None:
    annotation = parse_widget_annotation("@widget")
    assert annotation is not None
    assert (
        resolve_widget_class_name(
            annotation,
            layer_name="Bottom Nav",
            widget_suffix="Widget",
        )
        == "BottomNavWidget"
    )


def test_collect_widget_specs_annotated_product_card() -> None:
    card = CleanDesignTreeNode(
        id="card-1",
        name="@widget ProductCard",
        type=NodeType.CARD,
        sizing=Sizing(width=168.0, height=200.0),
        children=[
            CleanDesignTreeNode(
                id="card-1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Title",
                sizing=Sizing(width=120.0, height=20.0),
            ),
            CleanDesignTreeNode(
                id="card-1:body",
                name="Body",
                type=NodeType.TEXT,
                text="Body",
                sizing=Sizing(width=120.0, height=40.0),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[card],
    )
    config = WidgetExtractionConfig(policy="annotated")
    specs = collect_widget_specs(screen, {}, config=config)
    assert len(specs) == 1
    assert specs[0].class_name == "ProductCardWidget"
    assert card.extracted_widget_ref == "ProductCardWidget"


def test_render_annotated_widget_file() -> None:
    card = CleanDesignTreeNode(
        id="card-1",
        name="@widget ProductCard",
        type=NodeType.CARD,
        sizing=Sizing(width=168.0, height=200.0),
        children=[
            CleanDesignTreeNode(
                id="card-1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Hello",
                sizing=Sizing(width=120.0, height=20.0),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[card],
    )
    config = WidgetExtractionConfig(policy="annotated")
    specs = collect_widget_specs(screen, {}, config=config)
    result = render_cluster_widgets(specs, uses_svg=False, clean_trees=[screen])
    assert "lib/widgets/product_card_widget.dart" in result.files
    assert "class ProductCardWidget" in result.files["lib/widgets/product_card_widget.dart"]
