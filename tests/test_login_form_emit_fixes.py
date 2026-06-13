"""Login-form layout emit regressions (tray spacing, inputs, icons, headlines)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.flex_policy.alignment import (
    resolve_main_axis_alignment,
)
from figma_flutter_agent.generator.layout.flex_policy.column import (
    column_should_pin_footer_link_to_bottom,
)
from figma_flutter_agent.generator.layout.flex_policy.wrap import resolve_flex_wrap
from figma_flutter_agent.generator.layout.widgets.emit.text import _headline_prefers_single_line
from figma_flutter_agent.generator.layout.widgets.svg import render_filled_vector_leaf
from figma_flutter_agent.parser.interaction import (
    input_field_label_node,
    is_device_system_chrome_node,
    looks_like_password_field_stack,
)
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_column_stretch_main_axis_maps_to_start_not_space_between() -> None:
    column = CleanDesignTreeNode(
        id="col",
        name="Content",
        type=NodeType.COLUMN,
        alignment=Alignment(main="stretch"),
        children=[],
    )
    assert resolve_main_axis_alignment(column) == "MainAxisAlignment.start"


def test_device_chrome_does_not_expand_in_column() -> None:
    chrome = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FILL, height=34.0),
        children=[],
    )
    assert is_device_system_chrome_node(chrome)
    assert resolve_flex_wrap(parent_type=NodeType.COLUMN, node=chrome) is not None
    from figma_flutter_agent.generator.layout.flex_policy.wrap import FlexWrapKind

    assert resolve_flex_wrap(parent_type=NodeType.COLUMN, node=chrome) == FlexWrapKind.NONE


def test_input_password_hint_renders_stack_field_with_obscure_text() -> None:
    field = CleanDesignTreeNode(
        id="pwd",
        name="Input Field",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id="lbl",
                name="Password",
                type=NodeType.TEXT,
                text="Password",
                style=NodeStyle(font_size=12.0, text_color="0xFF6C7278"),
            ),
            CleanDesignTreeNode(
                id="surf",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=327.0, height=46.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_color="0xFFEDF1F3",
                    border_radius=10.0,
                ),
            ),
        ],
    )
    assert looks_like_password_field_stack(field)
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[field],
    )
    layout = render_layout_file(screen, feature_name="password_hint", uses_svg=False)[
        "lib/generated/password_hint_layout.dart"
    ]
    assert "obscureText: true" in layout
    assert "labelText: 'Input Field'" not in layout
    assert "Text('Password'" in layout


def test_input_external_label_not_used_as_textfield_hint() -> None:
    field = CleanDesignTreeNode(
        id="email",
        name="Input Field",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id="lbl",
                name="Email",
                type=NodeType.TEXT,
                text="Email",
                style=NodeStyle(font_size=12.0, text_color="0xFF6C7278"),
            ),
            CleanDesignTreeNode(
                id="surf",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=327.0, height=46.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_color="0xFFEDF1F3",
                    border_radius=10.0,
                ),
                children=[
                    CleanDesignTreeNode(
                        id="val",
                        name="Value",
                        type=NodeType.TEXT,
                        text="Loisbecket@gmail.com",
                        style=NodeStyle(font_size=16.0, text_color="0xFF1A1C1E"),
                    ),
                ],
            ),
        ],
    )
    assert input_field_label_node(field) is not None
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[field],
    )
    layout = render_layout_file(screen, feature_name="email_field", uses_svg=False)[
        "lib/generated/email_field_layout.dart"
    ]
    assert "Text('Email'" in layout
    assert "hintText: 'Email'" not in layout
    assert "Loisbecket@gmail.com" in layout


def test_auth_column_pins_footer_link_to_bottom() -> None:
    footer = CleanDesignTreeNode(
        id="footer",
        name="Footer",
        type=NodeType.TEXT,
        text="Don't have an account? Sign Up",
        sizing=Sizing(width=327.0, height=20.0),
    )
    form = CleanDesignTreeNode(
        id="form",
        name="Form",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="btn",
                name="Log In",
                type=NodeType.BUTTON,
                text="Log In",
                sizing=Sizing(width=327.0, height=48.0),
            ),
        ],
    )
    column = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        alignment=Alignment(main="spaceBetween"),
        sizing=Sizing(width=375.0, height_mode=SizingMode.FILL, height=700.0),
        children=[
            CleanDesignTreeNode(
                id="hdr",
                name="Header",
                type=NodeType.TEXT,
                text="Sign in",
                sizing=Sizing(width=327.0, height=32.0),
            ),
            form,
            footer,
        ],
    )
    assert column_should_pin_footer_link_to_bottom(column)
    assert resolve_main_axis_alignment(column) == "MainAxisAlignment.start"
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=812.0),
        children=[column],
    )
    layout = render_layout_file(screen, feature_name="auth_footer", uses_svg=False)[
        "lib/generated/auth_footer_layout.dart"
    ]
    assert "SingleChildScrollView" in layout
    assert "Sign Up" in layout
    assert "MainAxisAlignment.spaceBetween" not in layout


def test_extracted_input_widget_ref_is_inlined_not_const_stub() -> None:
    field = CleanDesignTreeNode(
        id="email",
        name="Email field",
        type=NodeType.INPUT,
        extracted_widget_ref="InputFieldWidget",
        sizing=Sizing(width=327.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id="lbl",
                name="Email",
                type=NodeType.TEXT,
                text="Email",
                style=NodeStyle(font_size=12.0),
            ),
            CleanDesignTreeNode(
                id="surf",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=327.0, height=46.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_radius=10.0,
                ),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[field],
    )
    layout = render_layout_file(screen, feature_name="inline_input", uses_svg=False)[
        "lib/generated/inline_input_layout.dart"
    ]
    assert "const InputFieldWidget()" not in layout
    assert "TextField" in layout


def test_headline_single_line_when_width_fits_copy() -> None:
    title = CleanDesignTreeNode(
        id="title",
        name="Title",
        type=NodeType.TEXT,
        text="Sign in to your Account",
        sizing=Sizing(width=327.0, height=42.0),
        style=NodeStyle(font_size=32.0, text_color="0xFF1A1C1E"),
    )
    assert _headline_prefers_single_line(title)
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=200.0),
        children=[title],
    )
    layout = render_layout_file(screen, feature_name="headline", uses_svg=False)[
        "lib/generated/headline_layout.dart"
    ]
    assert "FittedBox" in layout
    assert "Sign in to your Account" in layout


def test_filled_vector_leaf_emits_colored_box() -> None:
    vector = CleanDesignTreeNode(
        id="v1",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=8.0, height=8.0),
        style=NodeStyle(background_color="0xFF4285F4"),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=8.0, height=8.0),
    )
    expr = render_filled_vector_leaf(vector)
    assert expr is not None
    assert "Container(" in expr
    assert "0xFF4285F4" in expr
