"""Tests for checkbox and switch deterministic layout rendering."""

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.variant_props import variant_is_checked
from figma_flutter_agent.schemas import CleanDesignTreeNode, ComponentVariant, NodeType


def test_checked_checkbox_renders_true_value() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Remember me",
        type=NodeType.CHECKBOX,
        accessibility_label="Remember me",
        variant=ComponentVariant(
            component_id="c1",
            variant_properties={"State": "Selected"},
            state="Selected",
        ),
    )

    assert variant_is_checked(node) is True
    layout = render_layout_file(node, feature_name="settings", uses_svg=False)[
        "lib/generated/settings_layout.dart"
    ]

    assert "Checkbox(value: true" in layout
    assert "Remember me" in layout


def test_disabled_switch_renders_null_on_changed() -> None:
    node = CleanDesignTreeNode(
        id="2",
        name="Notifications",
        type=NodeType.SWITCH,
        accessibility_label="Notifications",
        variant=ComponentVariant(
            component_id="c2",
            variant_properties={"State": "Disabled"},
            state="Disabled",
        ),
    )

    layout = render_layout_file(node, feature_name="prefs", uses_svg=False)[
        "lib/generated/prefs_layout.dart"
    ]

    assert "Switch(value: false" in layout
    assert "onChanged: null" in layout


def test_cupertino_switch_renders_cupertino_widget() -> None:
    node = CleanDesignTreeNode(
        id="3",
        name="Wi-Fi",
        type=NodeType.SWITCH,
        variant=ComponentVariant(
            component_id="c3",
            variant_properties={"Checked": "true"},
        ),
    )

    layout = render_layout_file(
        node,
        feature_name="wifi",
        uses_svg=False,
        theme_variant="cupertino",
    )["lib/generated/wifi_layout.dart"]

    assert "CupertinoSwitch(value: true" in layout


def test_radio_group_renders_radio_list_tiles() -> None:
    group = CleanDesignTreeNode(
        id="1",
        name="Plan Radio Group",
        type=NodeType.RADIO_GROUP,
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Monthly",
                type=NodeType.TEXT,
                text="Monthly",
                variant=ComponentVariant(
                    component_id="c1",
                    variant_properties={"State": "Selected"},
                    state="Selected",
                ),
            ),
            CleanDesignTreeNode(id="3", name="Yearly", type=NodeType.TEXT, text="Yearly"),
        ],
    )

    layout = render_layout_file(group, feature_name="plan", uses_svg=False)[
        "lib/generated/plan_layout.dart"
    ]

    assert "RadioListTile<String>" in layout
    assert "groupValue: 'option_0'" in layout
    assert "Text('Monthly')" in layout


def test_dropdown_renders_menu_items() -> None:
    dropdown = CleanDesignTreeNode(
        id="1",
        name="Country Dropdown",
        type=NodeType.DROPDOWN,
        children=[
            CleanDesignTreeNode(id="2", name="USA", type=NodeType.TEXT, text="USA"),
            CleanDesignTreeNode(id="3", name="Canada", type=NodeType.TEXT, text="Canada"),
        ],
    )

    layout = render_layout_file(dropdown, feature_name="country", uses_svg=False)[
        "lib/generated/country_layout.dart"
    ]

    assert "DropdownButton<String>" in layout
    assert "DropdownMenuItem<String>" in layout
    assert "Text('USA')" in layout
    assert "custom-code:toggle-action" in layout or "onChanged:" in layout
