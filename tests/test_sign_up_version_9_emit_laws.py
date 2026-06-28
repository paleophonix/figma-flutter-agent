"""Regression laws for inline labeled input hosts (sign_up_version_9 family)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.flex_policy.stack import stack_should_flow_as_column
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.interaction.inline_input_hosts import (
    layout_fact_inline_labeled_input_field_host,
    layout_fact_phone_composite_field_host,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Padding, Sizing


def _inline_input_field_column(
    node_id: str,
    *,
    label: str,
    value: str,
    trailing_vector: CleanDesignTreeNode | None = None,
) -> CleanDesignTreeNode:
    value_row_children: list[CleanDesignTreeNode] = [
        CleanDesignTreeNode(
            id=f"{node_id}:value-wrap",
            name="Frame",
            type=NodeType.ROW,
            sizing=Sizing(width=200.0, height=21.0),
            children=[
                CleanDesignTreeNode(
                    id=f"{node_id}:value",
                    name=value,
                    type=NodeType.TEXT,
                    text=value,
                    sizing=Sizing(width=200.0, height=21.0),
                    style=NodeStyle(font_size=14.0, text_color="0xFF1A1C1E"),
                ),
            ],
        ),
    ]
    if trailing_vector is not None:
        value_row_children.append(trailing_vector)
    return CleanDesignTreeNode(
        id=node_id,
        name="Input Field",
        type=NodeType.COLUMN,
        spacing=2.0,
        sizing=Sizing(width=279.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:label",
                name="Title",
                type=NodeType.ROW,
                sizing=Sizing(width=59.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id=f"{node_id}:label-text",
                        name=label,
                        type=NodeType.TEXT,
                        text=label,
                        sizing=Sizing(width=59.0, height=19.0),
                        style=NodeStyle(font_size=12.0, text_color="0xFF6C7278"),
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id=f"{node_id}:surface",
                name="Input Area",
                type=NodeType.ROW,
                padding=Padding(top=27.0, bottom=27.0, left=14.0, right=14.0),
                sizing=Sizing(width=279.0, height=46.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_color="0xFFEDF1F3",
                    border_radius=10.0,
                    border_width=1.0,
                ),
                children=value_row_children,
            ),
        ],
    )


def test_inline_labeled_input_field_host_fact_matches_component_column() -> None:
    field = _inline_input_field_column("email", label="Email", value="Loisbecket@gmail.com")
    assert layout_fact_inline_labeled_input_field_host(field)


def test_inlined_input_host_emits_text_form_field_not_static_value() -> None:
    """Law: inlined_input_host_must_emit_functional_textfield_with_bounded_padding."""
    field = _inline_input_field_column("email", label="Email", value="Loisbecket@gmail.com")
    body = render_node_body(field, uses_svg=True, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "TextFormField" in compact
    assert "Text('Loisbecket@gmail.com'" not in compact
    assert "padding: const EdgeInsets.fromLTRB(14.0, 27.0, 14.0, 27.0)" not in compact
    assert "height: 46.0" in compact


def test_inline_input_host_binds_trailing_suffix_icon() -> None:
    trailing = CleanDesignTreeNode(
        id="eye",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=16.0, height=16.0),
        vector_asset_key="assets/icons/eye.svg",
        style=NodeStyle(has_stroke=True),
    )
    field = _inline_input_field_column(
        "password",
        label="Set Password",
        value="*******",
        trailing_vector=trailing,
    )
    body = render_node_body(field, uses_svg=True, parent_type=NodeType.COLUMN)
    assert "suffixIcon:" in body


def test_auth_stack_with_centered_logo_preserves_stack_layout() -> None:
    """Law: auth_absolute_stack_children_must_not_decompose_to_flow_column."""
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_9/processed.json").read_text(encoding="utf-8")
    )
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    assert stack_should_flow_as_column(root) is False


def test_sign_up_layout_emits_text_form_fields_and_positioned_logo() -> None:
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_9/processed.json").read_text(encoding="utf-8")
    )
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_laws", uses_svg=True)[
        "lib/generated/sign_up_version_9_laws_layout.dart"
    ]
    assert layout.count("TextFormField") >= 4
    assert "ellipse_1" in layout
    assert "Positioned(" in layout
    assert "centerLeft" not in layout.split("_buildLogo")[1].split("_buildContent")[0]


def test_phone_composite_field_host_fact_matches_country_prefix_column() -> None:
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_9/processed.json").read_text(encoding="utf-8")
    )
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    phone_form = None

    def find_phone_form(node: CleanDesignTreeNode) -> None:
        nonlocal phone_form
        if node.name == "Phone Form":
            phone_form = node
            return
        for child in node.children:
            find_phone_form(child)

    find_phone_form(root)
    assert phone_form is not None
    assert layout_fact_phone_composite_field_host(phone_form)


def test_sign_up_layout_emits_tappable_back_nav_and_bounded_phone_prefix() -> None:
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_9/processed.json").read_text(encoding="utf-8")
    )
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_nav_prefix", uses_svg=True)[
        "lib/generated/sign_up_version_9_nav_prefix_layout.dart"
    ]
    assert "back-nav" in layout
    assert "InkWell(" in layout
    assert "vector_I49_1740;4_70829.svg', width: 14.0, height: 8.0" in layout
    assert "fromLTRB(14.0, 27.0" not in layout
    assert "fromLTRB(14.0, 23.5" not in layout
    prefix = layout.split("prefix-dropdown")[1][:900]
    assert "11.5" in prefix
    assert "spacing: 7.0" in prefix


def test_sign_up_heading_emits_gradient_shader_not_theme_primary() -> None:
    """Law: text_fill_must_emit_source_gradient_or_color_not_theme_primary_fallback."""
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_9/processed.json").read_text(encoding="utf-8")
    )
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_heading", uses_svg=True)[
        "lib/generated/sign_up_version_9_heading_layout.dart"
    ]
    sign_up_index = layout.index("Text('Sign Up'")
    assert sign_up_index >= 0
    heading = layout[max(0, sign_up_index - 320) : sign_up_index + 320]
    assert "LinearGradient(" in heading
    assert "createShader(bounds)" in heading
    assert "0xFF4983F6" in heading
    assert "Colors.white" in heading
    assert "AppColors.primary" not in heading
    """Law: primary_cta_must_wire_interaction_not_empty_gesture."""
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_9/processed.json").read_text(encoding="utf-8")
    )
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_cta", uses_svg=True)[
        "lib/generated/sign_up_version_9_cta_layout.dart"
    ]
    assert "custom-code" in layout
    assert "onTap: () {}" not in layout.split("Register")[1][:400]
