"""Tests for checkbox and switch deterministic layout rendering."""

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.variant.state import variant_is_checked
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    Padding,
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


def test_input_flex_value_text_rejects_multiple_text_leaves() -> None:
    from figma_flutter_agent.parser.interaction import input_flex_value_text

    host = CleanDesignTreeNode(
        id="host",
        name="Input",
        type=NodeType.INPUT,
        children=[
            CleanDesignTreeNode(
                id="a",
                name="Email",
                type=NodeType.TEXT,
                text="Email",
            ),
            CleanDesignTreeNode(
                id="b",
                name="Value",
                type=NodeType.TEXT,
                text="user@example.com",
            ),
            CleanDesignTreeNode(
                id="c",
                name="Link",
                type=NodeType.TEXT,
                text="Forgot Password ?",
            ),
        ],
    )
    assert input_flex_value_text(host) is None


def test_composite_input_host_decomposes_nested_controls() -> None:
    trailing_icon = CleanDesignTreeNode(
        id="icon-btn",
        name="Icon",
        type=NodeType.BUTTON,
        sizing=Sizing(width=32.0, height=32.0),
        children=[
            CleanDesignTreeNode(
                id="vec",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/eye.svg",
                style=NodeStyle(has_stroke=True),
            )
        ],
    )
    form_host = CleanDesignTreeNode(
        id="form-host",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=428.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=12.0),
        children=[
            CleanDesignTreeNode(
                id="email-value",
                name="Value",
                type=NodeType.TEXT,
                text="user@example.com",
            ),
            CleanDesignTreeNode(
                id="link",
                name="Forgot",
                type=NodeType.TEXT,
                text="Forgot Password ?",
            ),
            CleanDesignTreeNode(
                id="login-btn",
                name="Button",
                type=NodeType.BUTTON,
                text="Log In",
                sizing=Sizing(width=327.0, height=48.0),
                style=NodeStyle(background_color="0xFF4D81E7", border_radius=8.0),
            ),
            CleanDesignTreeNode(
                id="divider",
                name="Or",
                type=NodeType.TEXT,
                text="Or",
            ),
            CleanDesignTreeNode(
                id="google-btn",
                name="Button",
                type=NodeType.BUTTON,
                text="Continue with Google",
                sizing=Sizing(width=327.0, height=48.0),
            ),
            trailing_icon,
        ],
    )
    body = render_node_body(form_host, uses_svg=False)
    assert "Column(" in body
    assert "TextFormField" not in body
    assert "initialValue:" not in body
    assert "user@example.comForgot" not in body
    assert body.count("button-action") >= 2


def test_forgot_password_hint_does_not_enable_obscure_text() -> None:
    from figma_flutter_agent.parser.interaction import input_hint_implies_obscure_text

    assert input_hint_implies_obscure_text("Forgot Password ?") is False
    assert input_hint_implies_obscure_text("Enter your password") is True


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
    assert "TextFormField" in body
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
    assert "border: Border.all(" in body
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
    assert "TextFormField" in body
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


def _stroke_vector(
    node_id: str,
    *,
    width: float,
    height: float,
    color: str = "0xFF52525C",
) -> CleanDesignTreeNode:
    from figma_flutter_agent.schemas import GeometryFrame, GeomRect, NodeStyle, Sizing

    paint_width = width if width > 0 else 1.4
    paint_height = height if height > 0 else 1.4
    return CleanDesignTreeNode(
        id=node_id,
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=width, height=height),
        style=NodeStyle(has_stroke=True, border_color=color),
        geometry_frame=GeometryFrame(
            paint_rect=GeomRect(width=paint_width, height=paint_height),
        ),
    )


def test_stroke_minus_button_emits_remove_icon() -> None:
    minus = CleanDesignTreeNode(
        id="281:12225",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=9999.0),
        children=[
            CleanDesignTreeNode(
                id="281:12226",
                name="SVG",
                type=NodeType.STACK,
                sizing=Sizing(width=16.0, height=16.0),
                children=[_stroke_vector("281:12227", width=9.3, height=0.0)],
            )
        ],
    )
    body = render_node_body(minus, uses_svg=False)
    assert "Icons.remove" in body
    assert "circle_outlined" not in body


def test_stroke_minus_in_stepper_row_uses_cluster_widget() -> None:
    minus = CleanDesignTreeNode(
        id="281:12225",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=9999.0),
        cluster_id="cluster_3",
        children=[
            CleanDesignTreeNode(
                id="281:12226",
                name="SVG",
                type=NodeType.STACK,
                sizing=Sizing(width=16.0, height=16.0),
                children=[_stroke_vector("281:12227", width=9.3, height=0.0)],
            )
        ],
    )
    plus = CleanDesignTreeNode(
        id="281:12230",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        style=NodeStyle(background_color="0xFF28A745", border_radius=9999.0),
        cluster_id="cluster_5",
        children=[
            CleanDesignTreeNode(
                id="281:12231",
                name="SVG",
                type=NodeType.STACK,
                sizing=Sizing(width=16.0, height=16.0),
                children=[
                    _stroke_vector("281:12232", width=9.3, height=0.0, color="0xFFFFFFFF"),
                    _stroke_vector("281:12233", width=0.0, height=9.3, color="0xFFFFFFFF"),
                ],
            )
        ],
    )
    row = CleanDesignTreeNode(
        id="281:12224",
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=213.0, height=48.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            minus,
            CleanDesignTreeNode(
                id="281:12229",
                name="Price",
                type=NodeType.STACK,
                sizing=Sizing(width_mode=SizingMode.FILL, width=120.0, height=26.0),
                children=[
                    CleanDesignTreeNode(
                        id="281:12229t",
                        name="86 ₽",
                        type=NodeType.TEXT,
                        text="86 ₽",
                    )
                ],
            ),
            plus,
        ],
    )
    body = render_node_body(
        row,
        uses_svg=False,
        cluster_classes={"cluster_3": "Cluster3Widget", "cluster_5": "Cluster5Widget"},
    )
    assert "const Cluster3Widget()" in body
    assert "MainAxisAlignment.spaceBetween" in body
    assert "Icons.circle_outlined" not in body


def test_stroke_plus_button_emits_add_icon_with_green_surface() -> None:
    plus = CleanDesignTreeNode(
        id="281:12230",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        style=NodeStyle(background_color="0xFF28A745", border_radius=9999.0),
        children=[
            CleanDesignTreeNode(
                id="281:12231",
                name="SVG",
                type=NodeType.STACK,
                sizing=Sizing(width=16.0, height=16.0),
                children=[
                    _stroke_vector("281:12232", width=9.3, height=0.0, color="0xFFFFFFFF"),
                    _stroke_vector("281:12233", width=0.0, height=9.3, color="0xFFFFFFFF"),
                ],
            )
        ],
    )
    body = render_node_body(plus, uses_svg=False)
    assert "Icons.add" in body
    assert "colorScheme.onPrimary" in body
    assert "calendar_today_outlined" not in body


def test_stroke_close_button_emits_close_icon() -> None:
    close = CleanDesignTreeNode(
        id="281:12218",
        name="Button - remove item",
        type=NodeType.BUTTON,
        sizing=Sizing(width=32.0, height=32.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=9999.0),
        children=[
            CleanDesignTreeNode(
                id="281:12219",
                name="SVG",
                type=NodeType.STACK,
                sizing=Sizing(width=16.0, height=16.0),
                children=[
                    _stroke_vector("281:12220", width=8.0, height=8.0),
                    _stroke_vector("281:12221", width=8.0, height=8.0),
                ],
            )
        ],
    )
    body = render_node_body(close, uses_svg=False)
    assert "Icons.close" in body


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
    assert "BoxDecoration" in body
    assert "borderRadius:" in body


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


def test_pruned_cluster_button_still_uses_cluster_widget() -> None:
    minus = CleanDesignTreeNode(
        id="281:12260",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=20.0),
        cluster_id="cluster_3",
        vector_asset_key="assets/icons/svg_281_12261.svg",
        flatten_figma_node_ids=["281:12261", "281:12262"],
        children=[],
    )
    body = render_node_body(
        minus,
        uses_svg=True,
        cluster_classes={"cluster_3": "Cluster3Widget"},
    )
    assert "const Cluster3Widget()" in body
    assert "Icons.circle_outlined" not in body


def test_pruned_cluster_stack_uses_cluster_widget() -> None:
    host = CleanDesignTreeNode(
        id="610:587",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            width=170.5,
            height_mode=SizingMode.FIXED,
            height=171.0,
        ),
        cluster_id="cluster_7",
        vector_asset_key="assets/icons/container_610_590.svg",
        flatten_figma_node_ids=["610:588", "610:589"],
        children=[],
    )
    body = render_node_body(
        host,
        uses_svg=True,
        parent_type=NodeType.COLUMN,
        cluster_classes={"cluster_7": "Cluster7Widget"},
    )
    assert "const Cluster7Widget()" in body
    assert "children: [Stack(clipBehavior" not in body


def _bonus_checkbox_label_row() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="281:12313",
        name="Label",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=56.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        padding=Padding(top=16.0, bottom=16.0, left=16.0, right=16.0),
        spacing=12.0,
        children=[
            CleanDesignTreeNode(
                id="281:12314",
                name="Input:margin",
                type=NodeType.COLUMN,
                sizing=Sizing(width=20.0, height=24.0),
                padding=Padding(top=4.0),
                children=[
                    CleanDesignTreeNode(
                        id="281:12315",
                        name="Input",
                        type=NodeType.INPUT,
                        sizing=Sizing(width=20.0, height=20.0),
                        style=NodeStyle(
                            background_color="0xFF28A745",
                            border_radius=2.5,
                        ),
                        accessibility_label="Input",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="281:12316",
                name="Bonus",
                type=NodeType.TEXT,
                text="Списать 135 бонусов.",
                sizing=Sizing(width=137.0, height=24.0),
                style=NodeStyle(
                    text_color="0xFF3F3F46",
                    font_size=13.0,
                    line_height=1.85,
                    text_align="LEFT",
                    glyph_top_offset=7.6,
                    glyph_height=12.2,
                ),
            ),
        ],
    )


def test_filled_bonus_checkbox_input_renders_checkbox_not_textfield() -> None:
    body = render_node_body(_bonus_checkbox_label_row(), uses_svg=False)
    assert "Checkbox(" in body
    assert "TextField(" not in body
    assert "Списать 135 бонусов." in body


def test_bounded_checkbox_label_row_centers_content_in_painted_band() -> None:
    from figma_flutter_agent.generator.layout.interactive_toggle import (
        toggle_checkbox_stateful_helpers,
    )

    body = render_node_body(_bonus_checkbox_label_row(), uses_svg=False)
    assert "Align(alignment: Alignment.centerLeft, child: Row(" in body
    assert "child: Center(child: _GeneratedToggleCheckbox(" in body
    assert "applyHeightToFirstAscent: false" in body
    assert "strutStyle" not in body
    helpers = toggle_checkbox_stateful_helpers()
    assert "MaterialTapTargetSize.shrinkWrap" in helpers
    assert "VisualDensity(horizontal: -4, vertical: -4)" in helpers


def test_green_plus_product_button_emits_add_icon() -> None:
    from figma_flutter_agent.parser.interaction import layout_fact_plus_icon_button

    button = CleanDesignTreeNode(
        id="610:553",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        style=NodeStyle(background_color="0xFF28A745", border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="610:555",
                name="Icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=14.0, height=14.0),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )
    assert layout_fact_plus_icon_button(button) is True
    body = render_node_body(button, uses_svg=False)
    assert "Icons.add" in body
    assert "calendar_today_outlined" not in body
    assert "favorite_border" not in body


def test_favorite_product_button_emits_heart_icon() -> None:
    button = CleanDesignTreeNode(
        id="610:541",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=32.0, height=32.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=16.0),
        children=[
            CleanDesignTreeNode(
                id="610:543",
                name="Icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=15.0, height=13.8),
                style=NodeStyle(background_color="0xFF3E4A3C"),
            )
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "Icons.favorite_border" in body
    assert "calendar_today_outlined" not in body


def test_icon_stepper_row_stretches_to_column_width() -> None:
    minus = CleanDesignTreeNode(
        id="281:12225",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        cluster_id="cluster_3",
        children=[],
    )
    plus = CleanDesignTreeNode(
        id="281:12230",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=40.0, height=40.0),
        cluster_id="cluster_5",
        children=[],
    )
    row = CleanDesignTreeNode(
        id="281:12224",
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=213.0, height=48.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            minus,
            CleanDesignTreeNode(
                id="281:12229",
                name="Price",
                type=NodeType.TEXT,
                text="86 ₽",
                sizing=Sizing(width_mode=SizingMode.FILL, width=120.0),
            ),
            plus,
        ],
    )
    body = render_node_body(
        row,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
        cluster_classes={
            "cluster_3": "Cluster3Widget",
            "cluster_5": "Cluster5Widget",
        },
    )
    assert "SizedBox(width: double.infinity" in body
    assert "MainAxisAlignment.spaceBetween" in body


def test_product_card_emits_edge_to_edge_hero_without_outer_padding() -> None:
    hero = CleanDesignTreeNode(
        id="610:539",
        name="Hero",
        type=NodeType.STACK,
        sizing=Sizing(width=170.5, height=171.0),
        children=[
            CleanDesignTreeNode(
                id="610:540",
                name="Image",
                type=NodeType.IMAGE,
                sizing=Sizing(width=171.0, height=171.0),
                image_asset_key="assets/images/image_610_540.png",
            )
        ],
    )
    meta = CleanDesignTreeNode(
        id="610:544",
        name="Meta",
        type=NodeType.COLUMN,
        padding=Padding(top=12.0, bottom=12.0, left=12.0, right=12.0),
        sizing=Sizing(width=170.5, height=143.5),
        children=[
            CleanDesignTreeNode(
                id="610:546",
                name="Label",
                type=NodeType.TEXT,
                text="КУЛИНАРИЯ",
            )
        ],
    )
    card = CleanDesignTreeNode(
        id="610:538",
        name="Product Card",
        type=NodeType.CARD,
        sizing=Sizing(width=170.5, height=310.5),
        style=NodeStyle(border_radius=22.0, elevation=3.5),
        children=[hero, meta],
    )
    body = render_node_body(card, uses_svg=False)
    assert "AppSpacing.md" not in body
    assert "clipBehavior: Clip.none" in body
    assert "ClipRRect(borderRadius: BorderRadius.vertical" in body.replace("\n", "")
    assert "mainAxisSize: MainAxisSize.min" in body
    assert "Expanded(child:" not in body


def test_space_between_total_row_from_cart_tree_has_no_flexible_children() -> None:
    import json
    from pathlib import Path

    import pytest

    dump_path = Path(r"E:/@dev/flutter-demo-project/ataev/.debug/processed/cart_layout.json")
    if not dump_path.is_file():
        pytest.skip("offline cart fixture unavailable")
    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    tree = CleanDesignTreeNode.model_validate(dump["cleanTree"])

    def find(node: CleanDesignTreeNode, target: str) -> CleanDesignTreeNode | None:
        if node.id == target:
            return node
        for child in node.children:
            found = find(child, target)
            if found is not None:
                return found
        return None

    row = find(tree, "281:12341")
    assert row is not None
    body = render_node_body(row, uses_svg=False)
    assert "MainAxisAlignment.spaceBetween" in body
    assert "CrossAxisAlignment.center" in body
    assert "Flexible(" not in body


def test_product_recommendation_hero_uses_cover_fill() -> None:
    hero = CleanDesignTreeNode(
        id="610:539",
        name="Hero",
        type=NodeType.STACK,
        sizing=Sizing(width=170.5, height=171.0),
        children=[
            CleanDesignTreeNode(
                id="610:540",
                name="Image",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=171.0, height=171.0),
                image_asset_key="assets/images/image_610_540.png",
            ),
            CleanDesignTreeNode(
                id="610:541",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width=32.0, height=32.0),
                style=NodeStyle(background_color="0xFFFFFFFF", border_radius=16.0),
                stack_placement=StackPlacement(right=8.0, top=8.0, width=32.0, height=32.0),
                children=[
                    CleanDesignTreeNode(
                        id="610:543",
                        name="Icon",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=15.0, height=13.8),
                        style=NodeStyle(background_color="0xFF3E4A3C"),
                    )
                ],
            ),
        ],
    )
    body = render_node_body(hero, uses_svg=False)
    assert "Positioned.fill(child: Image.asset" in body
    assert "BoxFit.cover" in body
    assert "favorite_border" in body


def test_compact_quantity_stepper_stack_renders_pill_row() -> None:
    stepper_stack = CleanDesignTreeNode(
        id="610:577",
        name="Background",
        type=NodeType.STACK,
        sizing=Sizing(width=152.2, height=28.0),
        children=[
            CleanDesignTreeNode(
                id="610:579",
                name="Minus",
                type=NodeType.COLUMN,
                cluster_id="cluster_15",
                children=[],
            ),
            CleanDesignTreeNode(
                id="610:581",
                name="Qty",
                type=NodeType.COLUMN,
                children=[
                    CleanDesignTreeNode(
                        id="610:582",
                        name="Text",
                        type=NodeType.TEXT,
                        text="1",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="610:583",
                name="Plus",
                type=NodeType.COLUMN,
                cluster_id="cluster_16",
                children=[],
            ),
            CleanDesignTreeNode(
                id="610:578",
                name="Pill",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=69.9, height=28.0),
                style=NodeStyle(background_color="0xFFFFFFFF", border_radius=32.0),
                children=[],
            ),
        ],
    )
    body = render_node_body(stepper_stack, uses_svg=False)
    compact = body.replace("\n", "")
    assert "SizedBox(width: 69.9" in compact
    assert "SizedBox(width: 152.2" not in compact
    assert "Icons.remove" in compact
    assert "Icons.add" in compact
    assert "Text('1'" in compact
    assert "Cluster15Widget" not in compact
    assert "Positioned(" not in compact
    assert "FittedBox(fit: BoxFit.scaleDown" not in compact
    assert "InkWell(" in compact
    assert "SizedBox(width: 24.0, height: 24.0" in compact
    assert "SizedBox(width: 32.0, height: 32.0" not in compact


def test_compact_stepper_uses_white_stroke_glyph_color() -> None:
    stroke_style = NodeStyle(
        has_stroke=True,
        border_width=2.0,
        border_color="0xFFFFFFFF",
    )
    stepper_stack = CleanDesignTreeNode(
        id="qty:stack",
        name="Qty",
        type=NodeType.STACK,
        sizing=Sizing(width=125.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="qty:minus",
                name="Minus",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="qty:minus:vec",
                        name="Vector",
                        type=NodeType.VECTOR,
                        style=stroke_style,
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="qty:text",
                name="Qty",
                type=NodeType.COLUMN,
                children=[
                    CleanDesignTreeNode(
                        id="qty:digit",
                        name="2",
                        type=NodeType.TEXT,
                        text="2",
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="qty:plus",
                name="Plus",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="qty:plus:vec",
                        name="Vector",
                        type=NodeType.VECTOR,
                        style=stroke_style,
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="qty:pill",
                name="Pill",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=125.0, height=48.0),
                style=NodeStyle(background_color="0xFFFF7622", border_radius=32.0),
            ),
        ],
    )
    body = render_node_body(stepper_stack, uses_svg=False)
    assert "Icons.remove" in body or "Icons.add" in body
    assert "color: Theme.of(context).colorScheme.primary" not in body


def test_compact_stepper_in_product_footer_uses_pill_width_not_stack_bbox() -> None:
    import json
    from pathlib import Path

    import pytest

    dump = Path(r"E:/@dev/flutter-demo-project/ataev/.debug/processed/cart_layout.json")
    if not dump.is_file():
        pytest.skip("offline cart fixture unavailable")
    from figma_flutter_agent.generator.normalize import normalize_clean_tree

    tree = CleanDesignTreeNode.model_validate(
        json.loads(dump.read_text(encoding="utf-8"))["cleanTree"]
    )
    norm = normalize_clean_tree(tree)

    def find(node: CleanDesignTreeNode, target: str) -> CleanDesignTreeNode | None:
        if node.id == target:
            return node
        for child in node.children:
            found = find(child, target)
            if found is not None:
                return found
        return None

    card = find(norm, "610:556")
    assert card is not None
    body = render_node_body(card, uses_svg=False).replace("\n", "")
    assert "stepper-decrease" in body
    assert "SizedBox(width: 152.2" not in body
    assert "SizedBox(width: 69.9" in body


def test_product_tile_metadata_column_uses_space_between_not_spacer() -> None:
    footer = CleanDesignTreeNode(
        id="1:footer",
        name="Footer",
        type=NodeType.COLUMN,
        padding=Padding(top=16.0),
        sizing=Sizing(width_mode=SizingMode.FILL, width=146.5, height=60.0),
        children=[
            CleanDesignTreeNode(
                id="1:price_row",
                name="Price",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, width=146.5, height=44.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:price",
                        name="Price",
                        type=NodeType.TEXT,
                        text="220₽",
                    )
                ],
            )
        ],
    )
    meta = CleanDesignTreeNode(
        id="1:meta",
        name="Meta",
        type=NodeType.COLUMN,
        padding=Padding(top=12.0, bottom=12.0, left=12.0, right=12.0),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=170.5,
            height=143.5,
        ),
        alignment=Alignment(main="spaceBetween", cross="stretch"),
        children=[
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.COLUMN,
                spacing=4.5,
                sizing=Sizing(width_mode=SizingMode.FILL, width=146.5, height=59.5),
                children=[
                    CleanDesignTreeNode(
                        id="1:label",
                        name="Label",
                        type=NodeType.TEXT,
                        text="ЗАВТРАКИ",
                    ),
                    CleanDesignTreeNode(
                        id="1:heading",
                        name="Heading",
                        type=NodeType.TEXT,
                        text="Панкейки",
                    ),
                ],
            ),
            footer,
        ],
    )
    body = render_node_body(meta, uses_svg=False)
    compact = body.replace("\n", "")
    assert "mainAxisSize: MainAxisSize.min" in compact
    assert "mainAxisAlignment: MainAxisAlignment.start" in compact
    assert "Spacer()" not in compact


def test_product_hero_renders_discount_badge_from_cart_tree() -> None:
    import json
    from pathlib import Path

    import pytest

    from figma_flutter_agent.generator.normalize import normalize_clean_tree
    from figma_flutter_agent.schemas import CleanDesignTreeNode

    dump_path = Path(r"E:/@dev/flutter-demo-project/ataev/.debug/processed/cart_layout.json")
    if not dump_path.is_file():
        pytest.skip("offline cart fixture unavailable")
    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    root = normalize_clean_tree(
        CleanDesignTreeNode.model_validate(dump["cleanTree"]),
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=Path(r"E:/@dev/flutter-demo-project/ataev"),
    )

    def find(node: CleanDesignTreeNode, target: str) -> CleanDesignTreeNode | None:
        if node.id == target:
            return node
        for child in node.children:
            found = find(child, target)
            if found is not None:
                return found
        return None

    hero = find(root, "610:557")
    if hero is None:
        import pytest

        pytest.skip("cart hero node not available on this machine")
    body = render_node_body(hero, uses_svg=False)
    compact = body.replace("\n", "")
    assert "image_610_558" in compact
    assert "-20%" in compact
    assert compact.count("Positioned(top: 10.0, left: 10.0") == 1


def test_product_hero_dedupes_nested_percent_badge_hosts() -> None:
    hero = CleanDesignTreeNode(
        id="1:hero",
        name="Hero",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=170.5, height=170.5),
        children=[
            CleanDesignTreeNode(
                id="1:img",
                name="Photo",
                type=NodeType.IMAGE,
                image_asset_key="assets/test.png",
            ),
            CleanDesignTreeNode(
                id="1:wrap",
                name="BadgeWrap",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=46.0, height=23.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:badge",
                        name="Badge",
                        type=NodeType.COLUMN,
                        sizing=Sizing(width_mode=SizingMode.FIXED, width=46.0, height=23.0),
                        children=[
                            CleanDesignTreeNode(
                                id="1:label",
                                name="Label",
                                type=NodeType.TEXT,
                                text="-20%",
                            )
                        ],
                    )
                ],
            ),
        ],
    )
    body = render_node_body(hero, uses_svg=False).replace("\n", "")
    assert "Text('-20%'" in body
    assert body.count("Positioned(top:") == 1
    assert "colorScheme.primary" in body


def test_product_card_footer_margin_skips_fixed_height_and_center_right_wrap() -> None:
    from figma_flutter_agent.generator.layout.flex_policy import (
        layout_fact_column_product_card_footer_margin,
    )

    footer = CleanDesignTreeNode(
        id="2:footer",
        name="Margin",
        type=NodeType.COLUMN,
        padding=Padding(top=16.0),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=146.5,
            height=56.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="2:price_row",
                name="PriceRow",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, width=146.5, height=40.0),
                children=[
                    CleanDesignTreeNode(
                        id="2:price",
                        name="Price",
                        type=NodeType.TEXT,
                        text="340₽",
                    ),
                    CleanDesignTreeNode(
                        id="2:plus",
                        name="Plus",
                        type=NodeType.BUTTON,
                        sizing=Sizing(width=40.0, height=40.0),
                        style=NodeStyle(background_color="0xFF28A745", border_radius=9999.0),
                        children=[],
                    ),
                ],
            )
        ],
    )
    assert layout_fact_column_product_card_footer_margin(footer)
    body = render_node_body(footer, uses_svg=False).replace("\n", "")
    assert "height: 56.0" not in body
    assert "Alignment.centerRight" not in body


def test_product_card_price_footer_row_centers_price_and_keeps_stepper_intrinsic() -> None:
    stepper = CleanDesignTreeNode(
        id="2:stepper",
        name="Stepper",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=152.2, height=28.0),
        children=[
            CleanDesignTreeNode(
                id="2:minus",
                name="Minus",
                type=NodeType.COLUMN,
                cluster_id="cluster_15",
                children=[],
            ),
            CleanDesignTreeNode(
                id="2:qty",
                name="Qty",
                type=NodeType.COLUMN,
                children=[
                    CleanDesignTreeNode(
                        id="2:qty_text",
                        name="Text",
                        type=NodeType.TEXT,
                        text="1",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="2:plus",
                name="Plus",
                type=NodeType.COLUMN,
                cluster_id="cluster_16",
                children=[],
            ),
            CleanDesignTreeNode(
                id="2:pill",
                name="Pill",
                type=NodeType.CONTAINER,
                style=NodeStyle(background_color="0xFFFFFFFF", border_radius=32.0),
                children=[],
            ),
        ],
    )
    price_row = CleanDesignTreeNode(
        id="2:price_row",
        name="PriceRow",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=146.5, height=44.0),
        children=[
            CleanDesignTreeNode(
                id="2:prices",
                name="Prices",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=76.2, height=44.0),
                children=[
                    CleanDesignTreeNode(
                        id="2:current",
                        name="Current",
                        type=NodeType.TEXT,
                        text="220₽",
                    ),
                    CleanDesignTreeNode(
                        id="2:old",
                        name="Old",
                        type=NodeType.TEXT,
                        text="275₽",
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="2:stepper_col",
                name="StepperCol",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=70.3, height=28.0),
                children=[
                    CleanDesignTreeNode(
                        id="2:stepper_row",
                        name="StepperRow",
                        type=NodeType.ROW,
                        sizing=Sizing(width_mode=SizingMode.FIXED, width=70.3, height=28.0),
                        children=[stepper],
                    )
                ],
            ),
        ],
    )
    body = render_node_body(price_row, uses_svg=False).replace("\n", "")
    assert "crossAxisAlignment: CrossAxisAlignment.center" in body
    assert "Expanded(child:" in body
    assert body.count("Expanded(child:") == 1
    assert "SizedBox(width: 70.3" in body
    stepper_slot = body.split("SizedBox(width: 70.3, child: Column", 1)[1]
    assert "CrossAxisAlignment.stretch" not in stepper_slot.split("InkWell(", 1)[0]


def test_favorite_icon_button_renders_without_pruned_children() -> None:
    button = CleanDesignTreeNode(
        id="610:541",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=32.0, height=32.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=9999.0),
        children=[
            CleanDesignTreeNode(
                id="610:543",
                name="Icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=15.0, height=13.8),
                style=NodeStyle(background_color="0xFF3E4A3C"),
            )
        ],
    )
    body = render_node_body(button, uses_svg=True)
    assert "Icons.favorite_border" in body
    assert "SizedBox.shrink()" not in body


def test_card_bounds_stack_child_height() -> None:
    stack = CleanDesignTreeNode(
        id="610:653",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(width=170.5, height=171.0),
        children=[
            CleanDesignTreeNode(
                id="610:654",
                name="Image",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=171.0, height=171.0),
            )
        ],
    )
    card = CleanDesignTreeNode(
        id="610:652",
        name="Card",
        type=NodeType.CARD,
        sizing=Sizing(width=206.0, height=200.0),
        children=[stack],
    )
    body = render_node_body(card, uses_svg=False)
    assert "SizedBox(width:" in body
    assert "height: 171.0" in body


def test_column_status_pill_centers_discount_label() -> None:
    pill = CleanDesignTreeNode(
        id="610:561",
        name="Background",
        type=NodeType.COLUMN,
        padding=Padding(top=4.0, bottom=4.0, left=8.0, right=8.0),
        sizing=Sizing(width=43.3, height=23.0),
        style=NodeStyle(background_color="0xFF28A745", border_radius=9999.0),
        children=[
            CleanDesignTreeNode(
                id="610:562",
                name="Text",
                type=NodeType.TEXT,
                text="-20%",
                sizing=Sizing(width=27.3, height=15.0),
                style=NodeStyle(font_size=12.0, font_weight="w600"),
            )
        ],
    )
    body = render_node_body(pill, uses_svg=False)
    assert "MainAxisAlignment.center" in body
    assert "EdgeInsets.symmetric(horizontal: 8.0" in body


def test_full_width_pill_button_skips_inner_padding() -> None:
    button = CleanDesignTreeNode(
        id="281:12346",
        name="Button",
        type=NodeType.BUTTON,
        padding=Padding(top=18.6, bottom=16.4, left=20.0, right=20.0),
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=56.0),
        style=NodeStyle(background_color="0xFF28A745", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="281:12347",
                name="Оформить заказ",
                type=NodeType.TEXT,
                text="Оформить заказ",
                style=NodeStyle(
                    font_size=14.0,
                    font_weight="w600",
                    text_align="CENTER",
                    line_height=1.5,
                ),
            )
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "EdgeInsets.fromLTRB(20.0, 18.6" not in body
    assert "Center(child:" in body


def test_square_product_photo_stack_renders_cover_image_and_scrim() -> None:
    from figma_flutter_agent.parser.interaction import layout_fact_cart_quantity_overlay

    overlay = CleanDesignTreeNode(
        id="281:12212",
        name="Overlay",
        type=NodeType.ROW,
        sizing=Sizing(width=96.0, height=96.0),
        style=NodeStyle(background_color="0xFF000000"),
        children=[
            CleanDesignTreeNode(
                id="281:12213",
                name="2",
                type=NodeType.TEXT,
                text="2",
                style=NodeStyle(font_size=36.0, font_weight="w600", text_align="CENTER"),
            )
        ],
    )
    assert layout_fact_cart_quantity_overlay(overlay) is True
    stack = CleanDesignTreeNode(
        id="281:12211",
        name="Photo",
        type=NodeType.STACK,
        sizing=Sizing(width=96.0, height=96.0),
        children=[
            CleanDesignTreeNode(
                id="610:745",
                name="image 17",
                type=NodeType.IMAGE,
                sizing=Sizing(width=252.7, height=169.2),
                image_asset_key="assets/images/image_17_610_745.png",
            ),
            overlay,
        ],
    )
    body = render_node_body(stack, uses_svg=False)
    assert "ClipRRect" in body
    assert "BoxFit.cover" in body
    assert "0x3D000000" in body
    assert "Cluster0Widget" not in body


def test_cart_thumbnail_button_finds_photo_in_column_stack_chain() -> None:
    overlay = CleanDesignTreeNode(
        id="281:12282",
        name="Overlay",
        type=NodeType.ROW,
        sizing=Sizing(width=96.0, height=96.0),
        style=NodeStyle(background_color="0xFF000000"),
        children=[
            CleanDesignTreeNode(
                id="281:12283",
                name="2",
                type=NodeType.TEXT,
                text="2",
                style=NodeStyle(font_size=36.0, font_weight="w600", text_align="CENTER"),
            )
        ],
    )
    button = CleanDesignTreeNode(
        id="281:12271",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=96.0, height=96.0),
        style=NodeStyle(border_radius=22.0),
        children=[
            CleanDesignTreeNode(
                id="281:12272",
                name="Photo",
                type=NodeType.COLUMN,
                sizing=Sizing(width=96.0, height=96.0),
                children=[
                    CleanDesignTreeNode(
                        id="281:12273",
                        name="PhotoStack",
                        type=NodeType.STACK,
                        sizing=Sizing(width=96.0, height=96.0),
                        children=[
                            CleanDesignTreeNode(
                                id="610:833",
                                name="image 19",
                                type=NodeType.IMAGE,
                                sizing=Sizing(width=376.1, height=210.0),
                                image_asset_key="assets/images/image_19_610_833.png",
                            ),
                        ],
                    ),
                ],
            ),
            overlay,
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "image_19_610_833.png" in body
    assert "ClipRRect" in body
    assert "Cluster0Widget" not in body


def test_cart_thumbnail_button_renders_pruned_overlay_quantity_digit() -> None:
    overlay = CleanDesignTreeNode(
        id="281:12282",
        name="Overlay",
        type=NodeType.ROW,
        cluster_id="cluster_0",
        sizing=Sizing(width=96.0, height=96.0),
        style=NodeStyle(background_color="0xFF000000"),
        flatten_figma_node_ids=["281:12282", "281:12283"],
        text="2",
        children=[],
    )
    button = CleanDesignTreeNode(
        id="281:12271",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=96.0, height=96.0),
        style=NodeStyle(border_radius=22.0),
        children=[
            CleanDesignTreeNode(
                id="281:12272",
                name="Photo",
                type=NodeType.COLUMN,
                sizing=Sizing(width=96.0, height=96.0),
                children=[
                    CleanDesignTreeNode(
                        id="281:12273",
                        name="PhotoStack",
                        type=NodeType.STACK,
                        sizing=Sizing(width=96.0, height=96.0),
                        children=[
                            CleanDesignTreeNode(
                                id="610:833",
                                name="image 19",
                                type=NodeType.IMAGE,
                                sizing=Sizing(width=376.1, height=210.0),
                                image_asset_key="assets/images/image_19_610_833.png",
                            ),
                        ],
                    ),
                ],
            ),
            overlay,
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "image_19_610_833.png" in body
    assert "Text('2'" in body
    assert "Cluster0Widget" not in body


def test_cart_thumbnail_button_renders_decomposed_photo_and_scrim() -> None:
    overlay = CleanDesignTreeNode(
        id="281:12212",
        name="Overlay",
        type=NodeType.ROW,
        sizing=Sizing(width=96.0, height=96.0),
        style=NodeStyle(background_color="0xFF000000"),
        children=[
            CleanDesignTreeNode(
                id="281:12213",
                name="2",
                type=NodeType.TEXT,
                text="2",
                style=NodeStyle(font_size=36.0, font_weight="w600", text_align="CENTER"),
            )
        ],
    )
    button = CleanDesignTreeNode(
        id="281:12210",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=96.0, height=96.0),
        style=NodeStyle(border_radius=22.0),
        children=[
            CleanDesignTreeNode(
                id="281:12211",
                name="Photo",
                type=NodeType.STACK,
                sizing=Sizing(width=96.0, height=96.0),
                children=[
                    CleanDesignTreeNode(
                        id="610:745",
                        name="image 17",
                        type=NodeType.IMAGE,
                        sizing=Sizing(width=252.7, height=169.2),
                        image_asset_key="assets/images/image_17_610_745.png",
                    ),
                ],
            ),
            overlay,
        ],
    )
    body = render_node_body(button, uses_svg=False)
    assert "ClipRRect" in body
    assert "image_17_610_745.png" in body
    assert "0x3D000000" in body
    assert "Cluster0Widget" not in body


def test_strikethrough_price_emits_line_through() -> None:
    node = CleanDesignTreeNode(
        id="1:old",
        name="Old price",
        type=NodeType.TEXT,
        text="275₽",
        style=NodeStyle(font_size=12.0, text_decoration="lineThrough"),
    )
    body = render_node_body(node, uses_svg=False)
    assert "TextDecoration.lineThrough" in body


def test_product_card_omits_expanded_metadata_slot() -> None:
    footer = CleanDesignTreeNode(
        id="1:footer",
        name="Footer",
        type=NodeType.COLUMN,
        padding=Padding(top=16.0),
        sizing=Sizing(width_mode=SizingMode.FILL, width=146.5, height=60.0),
        children=[
            CleanDesignTreeNode(
                id="1:price_row",
                name="Price",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, width=146.5, height=44.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:price",
                        name="Price",
                        type=NodeType.TEXT,
                        text="220₽",
                    )
                ],
            )
        ],
    )
    meta = CleanDesignTreeNode(
        id="1:meta",
        name="Meta",
        type=NodeType.COLUMN,
        padding=Padding(top=12.0, bottom=12.0, left=12.0, right=12.0),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=170.5,
            height=143.5,
        ),
        alignment=Alignment(main="spaceBetween", cross="stretch"),
        children=[
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.COLUMN,
                children=[
                    CleanDesignTreeNode(
                        id="1:heading",
                        name="Heading",
                        type=NodeType.TEXT,
                        text="Панкейки",
                    )
                ],
            ),
            footer,
        ],
    )
    hero = CleanDesignTreeNode(
        id="1:hero",
        name="Hero",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=170.5, height=170.5),
        children=[
            CleanDesignTreeNode(
                id="1:img",
                name="Photo",
                type=NodeType.IMAGE,
                image_asset_key="assets/test.png",
            )
        ],
    )
    card = CleanDesignTreeNode(
        id="1:card",
        name="Card",
        type=NodeType.CARD,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=170.5,
            height=314.5,
        ),
        children=[hero, meta],
    )
    body = render_node_body(card, uses_svg=False).replace("\n", "")
    assert "Expanded(child:" not in body
    assert "mainAxisSize: MainAxisSize.min" in body
    assert "clipBehavior: Clip.none" in body
    assert "SizedBox(height: 314.5" not in body


def test_product_tile_price_text_skips_metadata_rail_wrap() -> None:
    price_row = CleanDesignTreeNode(
        id="1:price_row",
        name="PriceRow",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=146.5, height=44.0),
        children=[
            CleanDesignTreeNode(
                id="1:prices",
                name="Prices",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL, width=48.0, height=44.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:current",
                        name="Current",
                        type=NodeType.TEXT,
                        text="220₽",
                        sizing=Sizing(width=48.0, height=20.0),
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:stepper",
                name="Stepper",
                type=NodeType.STACK,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=70.3, height=28.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:qty",
                        name="Qty",
                        type=NodeType.TEXT,
                        text="1",
                    )
                ],
            ),
        ],
    )
    body = render_node_body(price_row, uses_svg=False).replace("\n", "")
    assert (
        "FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerRight, child: Text('220₽'"
        not in body
    )


def test_product_hero_renders_clustered_badge_overlay() -> None:
    hero = CleanDesignTreeNode(
        id="1:hero",
        name="Hero",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=170.5, height=170.5),
        children=[
            CleanDesignTreeNode(
                id="1:img",
                name="Photo",
                type=NodeType.IMAGE,
                image_asset_key="assets/test.png",
            ),
            CleanDesignTreeNode(
                id="1:badge",
                name="Badge",
                type=NodeType.COLUMN,
                cluster_id="cluster_14",
                sizing=Sizing(width_mode=SizingMode.FIXED, width=46.0, height=23.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:label",
                        name="Label",
                        type=NodeType.TEXT,
                        text="-20%",
                    )
                ],
            ),
        ],
    )
    body = render_node_body(hero, uses_svg=False).replace("\n", "")
    assert "Text('-20%'" in body
    assert body.count("Positioned(top:") == 1
    assert "colorScheme.primary" in body


def test_space_between_total_row_flattens_label_and_price() -> None:
    row = CleanDesignTreeNode(
        id="281:12341",
        name="Background",
        type=NodeType.ROW,
        padding=Padding(top=16.0, bottom=16.0, left=16.0, right=16.0),
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=57.5),
        alignment=Alignment(main="spaceBetween", cross="center"),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=22.0),
        children=[
            CleanDesignTreeNode(
                id="281:12342",
                name="Container",
                type=NodeType.STACK,
                sizing=Sizing(width=61.6, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="281:12343",
                        name="К оплате",
                        type=NodeType.TEXT,
                        text="К оплате",
                        style=NodeStyle(font_size=14.0, font_weight="w600"),
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="281:12344",
                name="Container",
                type=NodeType.STACK,
                sizing=Sizing(width=58.7, height=25.5),
                children=[
                    CleanDesignTreeNode(
                        id="281:12345",
                        name="1088",
                        type=NodeType.TEXT,
                        text="1088 ₽",
                        style=NodeStyle(font_size=17.0, font_weight="w700"),
                    )
                ],
            ),
        ],
    )
    body = render_node_body(row, uses_svg=False)
    assert "MainAxisAlignment.spaceBetween" in body
    assert "CrossAxisAlignment.center" in body
    assert "Positioned(" not in body
    assert "textScalertextScaler" not in body
    assert "textScaler: textScaler" in body
    assert "leading: 0.7" not in body


def test_leaf_container_with_image_asset_key_emits_image_asset() -> None:
    node = CleanDesignTreeNode(
        id="610:540",
        name="Product photo",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=171.0, height=171.0),
        image_asset_key="assets/images/image_610_540.png",
    )
    body = render_node_body(node, uses_svg=False)
    assert "Image.asset('assets/images/image_610_540.png'" in body
    assert "SizedBox.shrink" not in body


def test_numeric_counter_badge_uses_square_circle_host() -> None:
    badge = CleanDesignTreeNode(
        id="1:badge",
        name="Background",
        type=NodeType.ROW,
        padding={"top": 4.0, "bottom": 4.0, "left": 9.2, "right": 9.2},
        sizing=Sizing(width=24.4, height=25.0, min_width=24.0),
        alignment=Alignment(main="center", cross="center"),
        style=NodeStyle(background_color="0xFF28A745", border_radius=35_791_400.0),
        children=[
            CleanDesignTreeNode(
                id="1:n",
                name="1",
                type=NodeType.TEXT,
                text="1",
                style=NodeStyle(
                    text_align="CENTER",
                    font_size=12.0,
                    font_weight="w700",
                    text_color="0xFFFFFFFF",
                ),
            )
        ],
    )
    body = render_node_body(badge, uses_svg=False)
    assert "BoxShape.circle" in body
    assert "width: 25.0, height: 25.0" in body
    assert "width: 24.4, height: 25.0" not in body
    assert "textHeightBehavior" in body
