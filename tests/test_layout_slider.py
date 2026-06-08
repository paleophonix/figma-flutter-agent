"""Tests for slider semantic layout rendering."""

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.variant.actions import slider_value_expr
from figma_flutter_agent.schemas import CleanDesignTreeNode, ComponentVariant, NodeType


def test_slider_value_from_variant_percent() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Volume",
        type=NodeType.SLIDER,
        variant=ComponentVariant(
            component_id="c1",
            variant_properties={"Value": "75"},
        ),
    )

    assert slider_value_expr(node) == "0.75"


def test_slider_renders_material_slider() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Brightness",
        type=NodeType.SLIDER,
        accessibility_label="Brightness",
        variant=ComponentVariant(
            component_id="c1",
            variant_properties={"Value": "0.25"},
        ),
    )

    layout = render_layout_file(node, feature_name="settings", uses_svg=False)[
        "lib/generated/settings_layout.dart"
    ]

    assert "Slider(value: 0.25" in layout
    assert "Text('Brightness')" in layout
    assert "custom-code:figma-1:slider-action" in layout


def test_disabled_slider_renders_null_on_changed() -> None:
    node = CleanDesignTreeNode(
        id="2",
        name="Volume",
        type=NodeType.SLIDER,
        variant=ComponentVariant(
            component_id="c2",
            variant_properties={"State": "Disabled"},
            state="Disabled",
        ),
    )

    layout = render_layout_file(
        node,
        feature_name="volume",
        uses_svg=False,
        theme_variant="cupertino",
    )["lib/generated/volume_layout.dart"]

    assert "CupertinoSlider(" in layout
    assert "onChanged: null" in layout
