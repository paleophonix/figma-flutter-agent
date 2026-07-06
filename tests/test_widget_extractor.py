from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.widget_extractor import (
    collect_cluster_widget_specs,
    render_cluster_widgets,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeType,
    Sizing,
    SizingMode,
)


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


def test_render_cluster_widgets_bounds_root_stack_height() -> None:
    stack = CleanDesignTreeNode(
        id="610:540",
        name="ImageHost",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            width=170.5,
            height_mode=SizingMode.FIXED,
            height=171.0,
        ),
        cluster_id="cluster_7",
        children=[
            CleanDesignTreeNode(
                id="610:541",
                name="Badge",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=32.0, height=32.0),
            )
        ],
    )
    tree = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[stack, stack],
    )
    specs = collect_cluster_widget_specs(tree, {"cluster_7": 2})
    result = render_cluster_widgets(specs, uses_svg=False)
    widget_path = f"lib/widgets/{specs[0].file_name}.dart"
    source = result.files[widget_path]
    assert "SizedBox(width:" in source
    assert "height: 171.0" in source


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


def test_generic_button_clusters_get_unique_class_names() -> None:
    """Repeated generic ``Button`` clusters must not collide on ``ButtonWidget``."""
    plus = CleanDesignTreeNode(
        id="1:plus",
        name="Button",
        type=NodeType.BUTTON,
        cluster_id="cluster_5",
        children=[CleanDesignTreeNode(id="1:icon", name="SVG", type=NodeType.STACK)],
    )
    add = CleanDesignTreeNode(
        id="2:add",
        name="Button",
        type=NodeType.BUTTON,
        cluster_id="cluster_8",
        children=[CleanDesignTreeNode(id="2:icon", name="SVG", type=NodeType.STACK)],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[plus, add, plus, add],
    )
    specs = collect_cluster_widget_specs(
        root,
        {"cluster_5": 2, "cluster_8": 2},
    )
    class_names = {spec.cluster_id: spec.class_name for spec in specs}
    assert class_names["cluster_5"] == "Cluster5Widget"
    assert class_names["cluster_8"] == "Cluster8Widget"
    assert class_names["cluster_5"] != class_names["cluster_8"]


def test_component_family_specs_prefers_default_variant_representative() -> None:
    """Repeated published component families must pick default/enabled representatives."""

    def _family_instance(instance_id: str, *, state: str) -> CleanDesignTreeNode:
        return CleanDesignTreeNode(
            id=instance_id,
            name="Chip",
            type=NodeType.CONTAINER,
            variant=ComponentVariant(
                component_id="comp-chip",
                component_name="Chip",
                state=state,
            ),
            children=[
                CleanDesignTreeNode(
                    id=f"{instance_id}:label",
                    name="Label",
                    type=NodeType.TEXT,
                    text="Label",
                ),
            ],
        )

    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            _family_instance("1:disabled", state="disabled"),
            _family_instance("2:default", state="default"),
        ],
    )

    specs = collect_cluster_widget_specs(root, {})

    assert len(specs) == 1
    assert specs[0].representative.variant is not None
    assert specs[0].representative.variant.state == "default"


def test_stroke_glyph_fallback_no_calendar_for_anonymous_vector() -> None:
    from figma_flutter_agent.generator.layout.widgets.decoration import (
        _render_stroke_glyph_fallback,
    )
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing

    node = CleanDesignTreeNode(
        id="anon:1",
        name="vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=16.0, height=16.0),
        style=NodeStyle(has_stroke=True, border_color="0xFF000000"),
    )
    assert _render_stroke_glyph_fallback(node) is None


def test_stroke_glyph_fallback_emits_divider_for_horizontal_hairline() -> None:
    from figma_flutter_agent.generator.layout.widgets.decoration import (
        _render_stroke_glyph_fallback,
    )
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing

    node = CleanDesignTreeNode(
        id="line:1",
        name="Line 1",
        type=NodeType.VECTOR,
        sizing=Sizing(width=347.0, height=1.0),
        style=NodeStyle(has_stroke=True, border_color="0xFFFFFFFF"),
    )
    body = _render_stroke_glyph_fallback(node)
    assert body is not None
    assert "Divider(" in body
    assert "Icons.remove" not in body
