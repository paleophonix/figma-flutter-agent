"""Tests for checkbox and switch deterministic layout rendering."""

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.generator.layout.widgets.render import render_node_body
from figma_flutter_agent.generator.variant_props import variant_is_checked
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


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


def test_flex_input_with_value_text_emits_text_field_not_static_column() -> None:
    field = CleanDesignTreeNode(
        id="362:346",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=317.0, height=52.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="362:347",
                name="Container",
                type=NodeType.COLUMN,
                sizing=Sizing(width=285.0, height=17.0),
                children=[
                    CleanDesignTreeNode(
                        id="362:348",
                        name="Ivan Ivanov",
                        type=NodeType.TEXT,
                        text="Ivan Ivanov",
                        sizing=Sizing(width=285.0, height=17.0),
                        style=NodeStyle(text_color="0xFF18181B", font_size=14.0),
                    )
                ],
            )
        ],
    )
    body = render_node_body(field, uses_svg=False)
    assert "TextField" in body
    assert "Material(color: Colors.transparent" in body
    assert "Text('Ivan Ivanov'" not in body


def test_decomposed_stack_child_gets_positioned_when_parent_is_stack() -> None:
    footer = CleanDesignTreeNode(
        id="611:1330",
        name="BottomNavBar",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=106.0),
        stack_placement=StackPlacement(
            vertical="BOTTOM",
            top=738.0,
            width=390.0,
            height=106.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="611:1338",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width=336.5, height=56.0),
                style=NodeStyle(background_color="0xFF28A745", border_radius=99.0),
                text="Save",
            ),
        ],
    )
    body = render_node_body(footer, uses_svg=False, parent_type=NodeType.STACK)
    assert "Positioned(" in body
    assert "bottom: 0.0" in body


def test_button_ink_border_uses_stroke_color_not_fill() -> None:
    button = CleanDesignTreeNode(
        id="btn",
        name="Card",
        type=NodeType.BUTTON,
        sizing=Sizing(width=317.0, height=131.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius=24.0,
            border_color="0xFFE4E4E7",
            border_width=1.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="row",
                name="Row",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, height=97.0),
            )
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "border: Border.all(color: Color(0xFFE4E4E7)" in body
    assert "border: Border.all(color: Color(0xFFFFFFFF)" not in body


def test_button_with_frame_fill_emits_ink_decoration() -> None:
    button = CleanDesignTreeNode(
        id="btn",
        name="Save",
        type=NodeType.BUTTON,
        sizing=Sizing(width=200.0, height=48.0),
        style=NodeStyle(background_color="0xFF28A745", border_radius=99.0),
        accessibility_label="Save",
        children=[
            CleanDesignTreeNode(
                id="lbl",
                name="Save",
                type=NodeType.TEXT,
                text="Save",
                sizing=Sizing(width=80.0, height=20.0),
                style=NodeStyle(text_color="0xFF000000", font_size=14.0),
            )
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "0xFF28A745" in body
    assert "Ink(" in body or "BoxDecoration" in body


def test_input_with_children_renders_column_not_single_placeholder() -> None:
    form = CleanDesignTreeNode(
        id="form",
        name="Form",
        type=NodeType.INPUT,
        sizing=Sizing(width=300.0, height=200.0),
        children=[
            CleanDesignTreeNode(
                id="field",
                name="Email",
                type=NodeType.INPUT,
                accessibility_label="Email",
            ),
            CleanDesignTreeNode(
                id="cta",
                name="Register",
                type=NodeType.BUTTON,
                text="Register",
            ),
        ],
    )
    body = render_node_body(form, uses_svg=False)
    assert "Column(" in body
    assert "TextField" in body
    assert "Register" in body
    assert "labelText: 'Input'" not in body


def test_flex_input_with_trailing_calendar_emits_row_and_icon() -> None:
    calendar = CleanDesignTreeNode(
        id="362:365",
        name="Button menu",
        type=NodeType.BUTTON,
        sizing=Sizing(width=18.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="362:366",
                name="image fill",
                type=NodeType.COLUMN,
                sizing=Sizing(width=18.0, height=18.0),
                children=[
                    CleanDesignTreeNode(
                        id="362:367",
                        name="image",
                        type=NodeType.STACK,
                        sizing=Sizing(width=14.0, height=13.0),
                        children=[
                            CleanDesignTreeNode(
                                id="362:368",
                                name="Vector",
                                type=NodeType.VECTOR,
                                sizing=Sizing(width=11.0, height=12.0),
                                style=NodeStyle(background_color="0xFF000000"),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    field = CleanDesignTreeNode(
        id="362:356",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=317.0, height=52.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="362:357",
                name="Container",
                type=NodeType.ROW,
                sizing=Sizing(width=285.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="362:360",
                        name="14",
                        type=NodeType.TEXT,
                        text="14.06.1995",
                        sizing=Sizing(width=82.0, height=21.0),
                        style=NodeStyle(text_color="0xFF18181B", font_size=14.0),
                    ),
                    calendar,
                ],
            )
        ],
    )
    body = render_node_body(field, uses_svg=False)
    assert "TextField" in body
    assert "calendar_today_outlined" in body or "Icons.calendar" in body
    assert "14.06.1995" in body


def test_compact_icon_back_button_emits_chevron() -> None:
    back = CleanDesignTreeNode(
        id="362:327",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=48.0, height=48.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=18.0),
        children=[
            CleanDesignTreeNode(
                id="362:328",
                name="SVG",
                type=NodeType.STACK,
                sizing=Sizing(width=20.0, height=20.0),
                children=[
                    CleanDesignTreeNode(
                        id="362:329",
                        name="Vector",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=5.0, height=10.0),
                        style=NodeStyle(
                            has_stroke=True,
                            border_color="0xFF52525C",
                        ),
                    )
                ],
            )
        ],
    )
    body = render_node_body(back, uses_svg=False)
    assert "chevron_left" in body


def test_avatar_row_emits_fill_container() -> None:
    avatar = CleanDesignTreeNode(
        id="362:336",
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width=80.0, height=80.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            CleanDesignTreeNode(
                id="362:337",
                name="И",
                type=NodeType.TEXT,
                text="И",
                sizing=Sizing(width=19.0, height=36.0),
                style=NodeStyle(text_color="0xFF2E7D32", font_size=24.0),
            )
        ],
    )
    body = render_node_body(avatar, uses_svg=False)
    assert "0xFFEEF9F0" in body
    assert "BoxDecoration" in body


def test_bottom_docked_sheet_has_top_radius_only() -> None:
    footer = CleanDesignTreeNode(
        id="611:1330",
        name="BottomNavBar",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=106.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=28.0),
        stack_placement=StackPlacement(
            vertical="BOTTOM",
            top=738.0,
            width=390.0,
            height=106.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="611:1338",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width=336.5, height=56.0),
                style=NodeStyle(background_color="0xFF28A745", border_radius=99.0),
                children=[
                    CleanDesignTreeNode(
                        id="611:1339",
                        name="Save",
                        type=NodeType.TEXT,
                        text="Сохранить изменения",
                        sizing=Sizing(width=154.0, height=21.0),
                        style=NodeStyle(text_color="0xFFFFFFFF", font_size=14.0),
                    )
                ],
            )
        ],
    )
    body = render_node_body(footer, uses_svg=False, parent_type=NodeType.STACK)
    assert "BorderRadius.only" in body
    assert "topLeft" in body
    assert "Center(child: Text" in body
