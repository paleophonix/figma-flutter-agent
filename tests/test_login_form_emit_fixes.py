"""Login-form emit regressions (E0-safe; no footer-pin / chrome WIP heuristics)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.interaction import is_link_text, looks_like_password_field_stack
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
)


def test_unsupported_vector_leaf_falls_back_to_shrink() -> None:
    vector = CleanDesignTreeNode(
        id="v-missing",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=8.0, height=8.0),
        style=NodeStyle(),
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=200.0),
        children=[vector],
    )
    layout = render_layout_file(screen, feature_name="vector_shrink", uses_svg=False)[
        "lib/generated/vector_shrink_layout.dart"
    ]
    assert "SizedBox.shrink()" in layout


def test_password_field_stack_matches_obscured_dot_geometry() -> None:
    field = CleanDesignTreeNode(
        id="pwd",
        name="Password field",
        type=NodeType.STACK,
        sizing=Sizing(width=327.0, height=46.0),
        children=[
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
                        id="dot1",
                        name="Dot",
                        type=NodeType.CONTAINER,
                        sizing=Sizing(width=8.0, height=8.0),
                        style=NodeStyle(background_color="0xFF1A1C1E"),
                    ),
                    CleanDesignTreeNode(
                        id="dot2",
                        name="Dot",
                        type=NodeType.CONTAINER,
                        sizing=Sizing(width=8.0, height=8.0),
                        style=NodeStyle(background_color="0xFF1A1C1E"),
                    ),
                    CleanDesignTreeNode(
                        id="dot3",
                        name="Dot",
                        type=NodeType.CONTAINER,
                        sizing=Sizing(width=8.0, height=8.0),
                        style=NodeStyle(background_color="0xFF1A1C1E"),
                    ),
                ],
            ),
        ],
    )
    assert looks_like_password_field_stack(field)


def test_is_link_text_detects_footer_sign_up_copy() -> None:
    assert is_link_text("Don't have an account? Sign Up")
    assert not is_link_text("Password")


def test_scroll_column_preserves_item_spacing_in_list_view() -> None:
    column = CleanDesignTreeNode(
        id="field",
        name="Field",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        spacing=32.0,
        sizing=Sizing(width=327.0, height=400.0),
        children=[
            CleanDesignTreeNode(
                id="headline",
                name="Headline",
                type=NodeType.TEXT,
                text="Title",
                sizing=Sizing(height=40.0),
            ),
            CleanDesignTreeNode(
                id="form",
                name="Form",
                type=NodeType.COLUMN,
                spacing=16.0,
                sizing=Sizing(height=200.0),
                children=[
                    CleanDesignTreeNode(
                        id="email",
                        name="Email",
                        type=NodeType.INPUT,
                        sizing=Sizing(width=327.0, height=69.0),
                        children=[
                            CleanDesignTreeNode(
                                id="surf",
                                name="Surface",
                                type=NodeType.CONTAINER,
                                sizing=Sizing(width=327.0, height=46.0),
                                style=NodeStyle(background_color="0xFFFFFFFF"),
                            )
                        ],
                    )
                ],
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[column],
    )
    layout = render_layout_file(screen, feature_name="scroll_spacing", uses_svg=False)[
        "lib/generated/scroll_spacing_layout.dart"
    ]
    assert "ListView(" in layout
    assert "SizedBox(height: 32.0)" in layout


def test_input_section_wrapper_emits_column_spacing() -> None:
    section = CleanDesignTreeNode(
        id="section",
        name="Input",
        type=NodeType.INPUT,
        spacing=24.0,
        sizing=Sizing(width=327.0, height=300.0),
        children=[
            CleanDesignTreeNode(
                id="fields",
                name="Field",
                type=NodeType.COLUMN,
                spacing=16.0,
                children=[
                    CleanDesignTreeNode(
                        id="forgot",
                        name="Forgot Password ?",
                        type=NodeType.TEXT,
                        text="Forgot Password ?",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="buttons",
                name="Buttons",
                type=NodeType.COLUMN,
                spacing=24.0,
                children=[
                    CleanDesignTreeNode(
                        id="cta",
                        name="Button",
                        type=NodeType.BUTTON,
                        sizing=Sizing(width=327.0, height=48.0),
                        style=NodeStyle(background_color="0xFF1D61E7"),
                        children=[
                            CleanDesignTreeNode(
                                id="lbl",
                                name="Log In",
                                type=NodeType.TEXT,
                                text="Log In",
                            )
                        ],
                    )
                ],
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[section],
    )
    layout = render_layout_file(screen, feature_name="input_spacing", uses_svg=False)[
        "lib/generated/input_spacing_layout.dart"
    ]
    assert "spacing: 24.0" in layout


def test_extracted_input_ref_inlines_text_field_not_widget_stub() -> None:
    field = CleanDesignTreeNode(
        id="email",
        name="Input Field",
        type=NodeType.INPUT,
        extracted_widget_ref="InputFieldWidget",
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
    assert "TextField" in layout or "TextFormField" in layout
    assert "textAlignVertical: TextAlignVertical.center" in layout
    assert "SizedBox(width: 327.0, height: 46.0, child:" in layout


def test_single_line_input_vertical_center_uniform() -> None:
    def _email_field(*, with_suffix: bool) -> CleanDesignTreeNode:
        surface_children: list[CleanDesignTreeNode] = []
        if with_suffix:
            surface_children.append(
                CleanDesignTreeNode(
                    id="eye",
                    name="Eye",
                    type=NodeType.BUTTON,
                    sizing=Sizing(width=16.0, height=16.0),
                )
            )
        return CleanDesignTreeNode(
            id="email" if not with_suffix else "password",
            name="Input Field",
            type=NodeType.INPUT,
            spacing=2.0,
            sizing=Sizing(width=327.0, height=69.0),
            children=[
                CleanDesignTreeNode(
                    id="lbl",
                    name="Email",
                    type=NodeType.TEXT,
                    text="Email" if not with_suffix else "Password",
                    style=NodeStyle(font_size=12.0, text_color="0xFF6C7278"),
                ),
                CleanDesignTreeNode(
                    id="surf",
                    name="Input Area",
                    type=NodeType.INPUT,
                    sizing=Sizing(width=327.0, height=46.0),
                    style=NodeStyle(
                        background_color="0xFFFFFFFF",
                        border_color="0xFFEDF1F3",
                        border_radius=10.0,
                    ),
                    children=surface_children,
                ),
            ],
        )

    for with_suffix in (False, True):
        screen = CleanDesignTreeNode(
            id="root",
            name="Screen",
            type=NodeType.STACK,
            sizing=Sizing(width=375.0, height=812.0),
            children=[_email_field(with_suffix=with_suffix)],
        )
        layout = render_layout_file(
            screen,
            feature_name=f"input_center_{with_suffix}",
            uses_svg=False,
        )[f"lib/generated/input_center_{with_suffix}_layout.dart"]
        assert "SizedBox(width: 327.0, height: 46.0, child:" in layout
        assert "Container(width: 327.0, height: 46.0, decoration:" in layout
        loose = "Container(width: 327.0, height: 46.0, decoration:"
        idx = layout.find(loose)
        assert idx >= 0
        snippet = layout[idx : idx + 220]
        assert "child: Material(" not in snippet
        assert "textAlignVertical: TextAlignVertical.center" in layout


def test_input_external_label_node_resolves_title_row_label() -> None:
    from figma_flutter_agent.parser.interaction.input_fields import (
        input_external_label_node,
    )

    nested = CleanDesignTreeNode(
        id="email:area",
        name="Input Area",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=46.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFEDF1F3",
            border_radius=10.0,
        ),
        children=[],
    )
    outer = CleanDesignTreeNode(
        id="email",
        name="Input Field",
        type=NodeType.INPUT,
        spacing=2.0,
        sizing=Sizing(width=327.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id="email:title",
                name="Title",
                type=NodeType.ROW,
                sizing=Sizing(width=327.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="email:lbl",
                        name="Email",
                        type=NodeType.TEXT,
                        text="Email",
                        sizing=Sizing(width=30.0, height=21.0),
                        style=NodeStyle(font_size=12.0, text_color="0xFF6C7278"),
                    ),
                ],
            ),
            nested,
        ],
    )
    label = input_external_label_node(outer)
    assert label is not None
    assert label.text == "Email"


def test_input_surface_node_resolves_nested_input_area_paint() -> None:
    from figma_flutter_agent.parser.interaction.input_fields import input_surface_node
    from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing

    nested = CleanDesignTreeNode(
        id="email:area",
        name="Input Area",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=46.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFEDF1F3",
            border_radius=10.0,
        ),
        children=[],
    )
    outer = CleanDesignTreeNode(
        id="email",
        name="Input Field",
        type=NodeType.INPUT,
        spacing=2.0,
        sizing=Sizing(width=327.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id="email:lbl",
                name="Email",
                type=NodeType.TEXT,
                text="Email",
                sizing=Sizing(width=30.0, height=21.0),
                style=NodeStyle(font_size=12.0, text_color="0xFF6C7278"),
            ),
            nested,
        ],
    )
    surface = input_surface_node(outer)
    assert surface is not None
    assert surface.id == nested.id


def test_login_dump_renders_inline_password_field() -> None:
    import json
    from pathlib import Path

    import pytest

    from figma_flutter_agent.generator.normalize import normalize_clean_tree
    from figma_flutter_agent.parser.tree import build_clean_tree

    dump = Path("sandbox/limbo/.debug/raw/login_version_1_layout.json")
    if not dump.is_file():
        pytest.skip("sandbox login dump not available")

    raw = json.loads(dump.read_text(encoding="utf-8"))
    tree, *_ = build_clean_tree(raw.get("root") or raw)
    tree = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        project_dir=Path("sandbox/limbo"),
    )
    layout = render_layout_file(
        tree,
        skip_layout_reconcile=True,
        feature_name="login_version_1",
        uses_svg=True,
        use_geometry_planner=True,
        package_name="inbox",
    )["lib/generated/login_version_1_layout.dart"]
    assert "const InputFieldWidget()" not in layout
    assert "obscureText: true" in layout
    assert "visibility_off" in layout
    assert "TextFormField" in layout or "TextField" in layout
    assert "Email" in layout
    assert "Password" in layout
    assert "softWrap: true" in layout
    assert "maxLines: 2" in layout
    assert "Expanded(child:" in layout
    assert "mainAxisSize: MainAxisSize.max" in layout
    assert "Color(0x1FFFFFFF)" in layout
    assert "right: 113.0" in layout
    assert "Align(alignment: Alignment.centerLeft" in layout
    assert "hintText" not in layout or "hintText: 'Email'" not in layout
    assert "height: 46.0" in layout
    assert "height: 69.0" not in layout
    assert "decoration: BoxDecoration" in layout
    assert "enabledBorder: InputBorder.none" in layout
    assert "SizedBox(width: 327.0, height: 46.0, child:" in layout
    assert "line_28_4024.svg', width: 140.5, height: 1.0" in layout
    assert "height: 3.0" not in layout.split("line_28_4024")[1][:200]
    assert layout.count("InkWell(") >= 2
    assert "customBorder" in layout


def test_geometry_multiline_headline_soft_wraps_with_width_box() -> None:
    from figma_flutter_agent.schemas import TextMetricsFrame

    headline = CleanDesignTreeNode(
        id="headline",
        name="Sign in to your Account",
        type=NodeType.TEXT,
        text="Sign in to your Account",
        sizing=Sizing(width=327.0, height=84.0),
        style=NodeStyle(
            font_size=32.0,
            font_weight="w700",
            text_color="0xFF1A1C1E",
            text_align="LEFT",
        ),
        text_metrics_frame=TextMetricsFrame(
            font_size=32.0,
            glyph_height=66.9,
            line_height_px=41.6,
            strut_height_ratio=1.3,
        ),
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=327.0, height=200.0),
        children=[headline],
    )
    layout = render_layout_file(screen, feature_name="headline_wrap", uses_svg=False)[
        "lib/generated/headline_wrap_layout.dart"
    ]
    assert "SizedBox(width: 327.0" in layout
    assert "Align(alignment: Alignment.centerLeft" in layout
    assert "softWrap: true" in layout
    assert "maxLines: 2" in layout
    assert "GestureDetector" not in layout
