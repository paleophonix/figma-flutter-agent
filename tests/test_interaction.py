"""Classic absolute stack interaction heuristics tests."""

import re

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.interaction import (
    layout_fact_back_nav_stack,
    layout_fact_checkbox_control,
    layout_fact_password_field_stack,
    stack_interaction_kind,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
    TextSpanPart,
)


def _input_stack() -> CleanDesignTreeNode:
    surface = CleanDesignTreeNode(
        id="2",
        name="FieldBg",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(background_color="0xFFF2F3F7", border_radius=15.0),
    )
    label = CleanDesignTreeNode(
        id="3",
        name="Email address",
        type=NodeType.TEXT,
        text="Email address",
        style=NodeStyle(
            text_color="0xFFA1A4B2",
            font_size=16.0,
            font_weight="w300",
            line_height=1.08,
            letter_spacing=0.8,
        ),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=20.0,
            top=22.0,
            width=120.0,
            height=17.8,
        ),
    )
    return CleanDesignTreeNode(
        id="1",
        name="Email",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=400),
        children=[surface, label],
    )


def test_stack_interaction_kind_treats_start_chip_as_button() -> None:
    surface = CleanDesignTreeNode(
        id="2",
        name="Rectangle 14",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=70.0, height=35.0),
        style=NodeStyle(background_color="0xFFEBEAEC", border_radius=25.0),
    )
    label = CleanDesignTreeNode(
        id="3",
        name="START",
        type=NodeType.TEXT,
        text="START",
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=15.0,
            top=10.0,
            width=41.0,
            height=14.0,
        ),
    )
    start = CleanDesignTreeNode(
        id="1",
        name="Group 20",
        type=NodeType.STACK,
        sizing=Sizing(width=70.0, height=35.0),
        children=[surface, label],
    )
    assert stack_interaction_kind(start) == "button"


def test_stack_interaction_kind_detects_input_and_button() -> None:
    assert stack_interaction_kind(_input_stack()) == "input"

    button_bg = CleanDesignTreeNode(
        id="5",
        name="Google",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(border_color="0xFFEBEAEC", border_width=1.0, border_radius=38.0),
    )
    button_label = CleanDesignTreeNode(
        id="6",
        name="Label",
        type=NodeType.TEXT,
        text="CONTINUE WITH GOOGLE",
    )
    button = CleanDesignTreeNode(
        id="4",
        name="GoogleBtn",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        children=[button_bg, button_label],
    )
    assert stack_interaction_kind(button) == "button"


def test_stack_interaction_kind_treats_nested_social_shell_as_button() -> None:
    """Outer social row stays a button when Figma wraps surface+label in an inner stack."""
    inner_surface = CleanDesignTreeNode(
        id="3",
        name="Rectangle",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(border_color="0xFFEBEAEC", border_width=1.0, border_radius=38.0),
    )
    inner_label = CleanDesignTreeNode(
        id="4",
        name="Label",
        type=NodeType.TEXT,
        text="CONTINUE WITH GOOGLE",
    )
    inner = CleanDesignTreeNode(
        id="2",
        name="Inner",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        children=[inner_surface, inner_label],
    )
    outer = CleanDesignTreeNode(
        id="1",
        name="GoogleBtn",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        children=[inner],
    )
    assert stack_interaction_kind(outer) == "button"


def test_input_stack_renders_text_field() -> None:
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[_input_stack()],
    )
    layout = render_layout_file(screen, feature_name="email", uses_svg=False)[
        "lib/generated/email_layout.dart"
    ]
    assert "TextField(" in layout
    assert "InputDecoration(" in layout
    assert "hintText: 'Email address'" in layout
    assert "374.0" in layout and "63.0" in layout
    assert "hintStyle:" in layout or "decoration: InputDecoration" in layout
    assert "contentPadding: EdgeInsets.fromLTRB(20.0, 22.0, 20.0," in layout
    assert "height: 1.08" in layout
    assert "Text('Email address'" not in layout


def test_button_node_children_stack_gets_rounded_inkwell_and_positioned() -> None:
    surface = CleanDesignTreeNode(
        id="3",
        name="Bg",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(background_color="0xFF7583CA", border_radius=38.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=0, top=0),
    )
    label = CleanDesignTreeNode(
        id="4",
        name="Label",
        type=NodeType.TEXT,
        text="CONTINUE WITH FACEBOOK",
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=20),
    )
    button = CleanDesignTreeNode(
        id="2",
        name="Facebook",
        type=NodeType.BUTTON,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=100),
        children=[surface, label],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[button],
    )
    layout = render_layout_file(screen, feature_name="facebook", uses_svg=False)[
        "lib/generated/facebook_layout.dart"
    ]
    assert "child: Ink(" in layout
    assert "BoxDecoration(" in layout
    assert "onTap: () { /* <custom-code:figma-2:button-action> */ }" in layout
    assert "borderRadius: BorderRadius.circular(38.0)" in layout


def test_form_field_stack_without_hint_keyword_renders_text_field() -> None:
    surface = CleanDesignTreeNode(
        id="2",
        name="FieldBg",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(background_color="0xFFF2F3F7", border_radius=15.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=0, top=0),
    )
    value = CleanDesignTreeNode(
        id="3",
        name="Name",
        type=NodeType.TEXT,
        text="afsar",
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=20.0,
            top=22.0,
            width=120.0,
            height=14.0,
        ),
    )
    field = CleanDesignTreeNode(
        id="1",
        name="NameField",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=300),
        children=[surface, value],
    )
    assert stack_interaction_kind(field) == "input"
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[field],
    )
    layout = render_layout_file(screen, feature_name="name", uses_svg=False)[
        "lib/generated/name_layout.dart"
    ]
    assert "TextField(" in layout
    assert "Text('afsar'" not in layout


def test_password_dot_stack_renders_obscured_text_field() -> None:
    surface = CleanDesignTreeNode(
        id="2",
        name="FieldBg",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(background_color="0xFFF2F3F7", border_radius=15.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=0, top=0),
    )
    dots = [
        CleanDesignTreeNode(
            id=f"dot-{index}",
            name=f"Ellipse {index}",
            type=NodeType.CONTAINER,
            sizing=Sizing(width=6.9, height=6.9),
            style=NodeStyle(background_color="0xFF3F414E"),
            stack_placement=StackPlacement(
                horizontal="LEFT", vertical="TOP", left=float(index * 10)
            ),
        )
        for index in range(4)
    ]
    field = CleanDesignTreeNode(
        id="1",
        name="Password",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=500),
        children=[surface, *dots],
    )
    assert layout_fact_password_field_stack(field)
    assert stack_interaction_kind(field) == "input"
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[field],
    )
    layout = render_layout_file(screen, feature_name="password", uses_svg=False)[
        "lib/generated/password_layout.dart"
    ]
    assert "TextField(" in layout
    assert "obscureText: true" in layout


def test_checkbox_control_renders_checkbox_widget() -> None:
    box = CleanDesignTreeNode(
        id="1",
        name="Checkbox",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=24.2, height=24.2),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFA1A4B2",
            border_width=2.0,
            border_radius=4.0,
        ),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=360, top=700),
    )
    assert layout_fact_checkbox_control(box)
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[box],
    )
    layout = render_layout_file(screen, feature_name="consent", uses_svg=False)[
        "lib/generated/consent_layout.dart"
    ]
    assert "Checkbox(" in layout
    assert "onChanged:" in layout


def test_input_named_checkbox_square_renders_checkbox_widget() -> None:
    box = CleanDesignTreeNode(
        id="1",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=20.0, height=20.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFF767676",
            border_width=1.0,
            border_radius=2.5,
        ),
    )
    assert layout_fact_checkbox_control(box)
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.ROW,
        sizing=Sizing(width=414.0, height=896.0),
        children=[box],
    )
    layout = render_layout_file(screen, feature_name="options", uses_svg=False)[
        "lib/generated/options_layout.dart"
    ]
    assert "_GeneratedToggleCheckbox(" in layout
    assert "setState(() => _value = next ?? false)" in layout
    assert "TextField(" not in layout


def test_colored_category_icon_tile_is_not_checkbox_control() -> None:
    icon_tile = CleanDesignTreeNode(
        id="tile",
        name="Category",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        style=NodeStyle(background_color="0xFFE7F0FF", border_radius=8.0),
        stack_placement=StackPlacement(left=300.0, top=200.0, width=24.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Briefcase",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/briefcase.svg",
                sizing=Sizing(width=16.0, height=16.0),
                stack_placement=StackPlacement(left=4.0, top=4.0, width=16.0, height=16.0),
            ),
        ],
    )
    label = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        text="Task title",
        stack_placement=StackPlacement(left=24.0, top=200.0, width=180.0, height=20.0),
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[label, icon_tile],
    )

    assert not layout_fact_checkbox_control(icon_tile)

    layout = render_layout_file(screen, feature_name="card_row", uses_svg=True)[
        "lib/generated/card_row_layout.dart"
    ]
    assert "consent-row" not in layout
    assert "_GeneratedToggleCheckbox(" not in layout
    assert "Checkbox(" not in layout


def test_stroked_outline_square_is_checkbox_control() -> None:
    """Stroke-only vector inside a compact square is an interactive checkbox, not a static icon."""
    outline = CleanDesignTreeNode(
        id="cb",
        name="player-stop",
        type=NodeType.STACK,
        sizing=Sizing(width=19.0, height=19.0),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/outline.svg",
                sizing=Sizing(width=11.0, height=11.0),
                style=NodeStyle(has_stroke=True, border_width=1.5, border_color="0xFF6C7278"),
                stack_placement=StackPlacement(left=4.0, top=4.0, width=11.0, height=11.0),
            ),
        ],
        stack_placement=StackPlacement(left=20.0, top=700.0, width=19.0, height=19.0),
    )
    assert layout_fact_checkbox_control(outline)
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[outline],
    )
    layout = render_layout_file(screen, feature_name="outline_cb", uses_svg=True)[
        "lib/generated/outline_cb_layout.dart"
    ]
    assert "Checkbox(" in layout
    assert "onChanged:" in layout


def test_back_nav_stack_renders_inkwell() -> None:
    circle = CleanDesignTreeNode(
        id="2",
        name="Circle",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=55.0, height=55.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFEBEAEC",
            border_width=1.0,
            border_radius=28.0,
        ),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=0, top=0),
    )
    arrow = CleanDesignTreeNode(
        id="3",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/back.svg",
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=18, top=18),
    )
    back = CleanDesignTreeNode(
        id="1",
        name="Back",
        type=NodeType.STACK,
        sizing=Sizing(width=55.0, height=55.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=50),
        children=[circle, arrow],
    )
    assert layout_fact_back_nav_stack(back)
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[back],
    )
    layout = render_layout_file(screen, feature_name="back", uses_svg=False)[
        "lib/generated/back_layout.dart"
    ]
    assert "Positioned(left: 20.0, top: 50.0" in layout
    assert "Stack(clipBehavior:" in layout


def test_button_stack_renders_inkwell() -> None:
    button_bg = CleanDesignTreeNode(
        id="2",
        name="Google",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(border_color="0xFFEBEAEC", border_width=1.0, border_radius=38.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=0, top=0),
    )
    button_label = CleanDesignTreeNode(
        id="3",
        name="Label",
        type=NodeType.TEXT,
        text="CONTINUE WITH GOOGLE",
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=80, top=20),
    )
    button = CleanDesignTreeNode(
        id="1",
        name="GoogleBtn",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=200),
        children=[button_bg, button_label],
    )
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[button],
    )
    layout = render_layout_file(screen, feature_name="google", uses_svg=False)[
        "lib/generated/google_layout.dart"
    ]
    assert "child: Ink(" in layout
    assert "onTap: () { /* <custom-code:figma-1:button-action> */ }" in layout
    assert "borderRadius: BorderRadius.circular(38.0)" in layout
    assert "border: Border.all(" in layout
    assert "AppColors.primary" in layout or "colorScheme.onPrimary" in layout


def test_button_stack_positioned_has_bounds_when_wrapped_in_inkwell() -> None:
    """``Material``/``InkWell`` wrappers must not skip ``Positioned`` width/height pins."""
    button_bg = CleanDesignTreeNode(
        id="2",
        name="Google",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(border_color="0xFFEBEAEC", border_width=1.0, border_radius=38.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=0, top=0),
    )
    button_label = CleanDesignTreeNode(
        id="3",
        name="Label",
        type=NodeType.TEXT,
        text="CONTINUE WITH GOOGLE",
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=80, top=20),
    )
    button = CleanDesignTreeNode(
        id="1",
        name="GoogleBtn",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=200),
        children=[button_bg, button_label],
    )
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[button],
    )
    layout = render_layout_file(screen, feature_name="google_bounds", uses_svg=False)[
        "lib/generated/google_bounds_layout.dart"
    ]
    assert re.search(
        r"Positioned\(left: 20\.0, top: 200\.0, width: 374\.0, height: 63\.0,"
        r" (?:key: ValueKey\('[^']+'\), )?child: "
        r"(?:SizedBox\(width: 374\.0, height: 63\.0, child: )?Material\(",
        layout,
    )


def test_rich_text_renders_text_rich() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Footer",
        type=NodeType.TEXT,
        text="ALREADY HAVE AN ACCOUNT? SIGN UP",
        style=NodeStyle(font_size=14.0, text_align="CENTER"),
        text_spans=[
            TextSpanPart(text="ALREADY HAVE AN ACCOUNT? ", text_color="0xFFA1A4B2"),
            TextSpanPart(text="SIGN UP", text_color="0xFF8E97FD", font_weight="w700", is_link=True),
        ],
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=800),
    )
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[node],
    )
    layout = render_layout_file(screen, feature_name="footer", uses_svg=False)[
        "lib/generated/footer_layout.dart"
    ]
    assert "Text.rich(" in layout
    assert "TextSpan(text: 'SIGN UP'" in layout
    assert "TapGestureRecognizer()..onTap = () {}" in layout
    assert "fontWeight: FontWeight.w700" in layout or "TextSpan(text: 'SIGN UP'" in layout
    assert "textAlign: TextAlign.center" in layout
