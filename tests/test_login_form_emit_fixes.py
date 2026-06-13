"""E0-safe layout emit contracts (no name/text shortcut assertions)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets import svg as svg_widgets
from figma_flutter_agent.parser.interaction import is_link_text, looks_like_password_field_stack
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
)
from figma_flutter_agent.schemas.geometry import StackPlacement


def test_vector_without_asset_emits_no_filled_leaf_helper() -> None:
    """Filled vectors must not use ad-hoc ``Container`` color-box fallback helpers."""
    assert not hasattr(svg_widgets, "render_filled_vector_leaf")

    vector = CleanDesignTreeNode(
        id="v1",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=8.0, height=8.0),
        style=NodeStyle(background_color="0xFF4285F4"),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=8.0, height=8.0),
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        children=[vector],
    )
    layout = render_layout_file(screen, feature_name="vector_leaf", uses_svg=False)[
        "lib/generated/vector_leaf_layout.dart"
    ]
    assert "render_filled_vector_leaf" not in layout
    assert "Container(width:" not in layout
    assert "Icon(" not in layout
    assert "SizedBox.shrink()" in layout


def test_password_stack_without_text_hint_does_not_classify_input_node() -> None:
    """``looks_like_password_field_stack`` remains stack-geometry based (not INPUT name hints)."""
    field = CleanDesignTreeNode(
        id="pwd",
        name="Password field",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id="lbl",
                name="Password",
                type=NodeType.TEXT,
                text="Password",
                style=NodeStyle(font_size=12.0),
            ),
        ],
    )
    assert not looks_like_password_field_stack(field)


def test_login_compact_form_fields_emit_password_label_and_obscure_text() -> None:
    """Compact paired INPUT clusters emit captioned fields, not generic ``render_input`` stubs."""
    from pathlib import Path

    import json

    from figma_flutter_agent.generator.normalize import reconcile_layout_tree
    from figma_flutter_agent.parser.tree import build_clean_tree

    raw = json.loads(
        Path("sandbox/limbo/.debug/raw/login_version_1_layout.json").read_text(encoding="utf-8")
    )
    root = raw.get("root") or raw
    tree, *_ = build_clean_tree(root)
    tree = reconcile_layout_tree(tree)
    layout = render_layout_file(tree, feature_name="login_version_1", uses_svg=False)[
        "lib/generated/login_version_1_layout.dart"
    ]
    assert "labelText: 'Input Field'" not in layout
    assert "Text('Email'" in layout or "Text('Email'," in layout
    assert "Text('Password'" in layout or "Text('Password'," in layout
    assert layout.count("obscureText: true") == 1
    assert "Sign in to your\\nAccount" in layout or "Sign in to your\nAccount" in layout
    assert "Colors.black" in layout


def test_forgot_password_is_link_text_not_field_label() -> None:
    assert is_link_text("Forgot Password ?")


def test_headline_sign_in_title_is_not_link_text() -> None:
    assert not is_link_text("Sign in to your Account")
