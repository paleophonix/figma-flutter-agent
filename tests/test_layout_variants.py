"""Tests for component variant wiring in deterministic layout output."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, ComponentVariant, NodeType


def test_disabled_button_renders_null_on_pressed() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    def mark_disabled(node: CleanDesignTreeNode) -> None:
        if node.type == NodeType.BUTTON:
            node.variant = ComponentVariant(
                component_id="comp-1",
                state="Disabled",
                variant_properties={"State": "Disabled"},
            )
        for child in node.children:
            mark_disabled(child)

    mark_disabled(tree)
    layout = render_layout_file(tree, feature_name="onboarding", uses_svg=False)[
        "lib/generated/onboarding_layout.dart"
    ]

    assert "onPressed: null" in layout or "onTap: null" in layout
    assert "app_spacing.dart" in layout
    assert "app_colors.dart" in layout


def test_catalog_layout_uses_theme_spacing() -> None:
    root = json.loads(Path("tests/fixtures/figma_cards_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)
    layout = render_layout_file(tree, feature_name="catalog_screen", uses_svg=False)[
        "lib/generated/catalog_screen_layout.dart"
    ]

    assert "AppSpacing.md" in layout or "AppElevation.md" in layout


def test_secondary_button_renders_outlined() -> None:
    button = CleanDesignTreeNode(
        id="button",
        name="Continue",
        type=NodeType.BUTTON,
        text="Continue",
        variant=ComponentVariant(
            component_id="comp-1",
            variant_properties={"Type": "Secondary", "Size": "Large"},
        ),
    )

    layout = render_layout_file(button, feature_name="onboarding", uses_svg=False)[
        "lib/generated/onboarding_layout.dart"
    ]

    assert "OutlinedButton(" in layout
    assert "AppSpacing.lg" in layout


def test_password_input_renders_obscure_text() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Password",
        type=NodeType.INPUT,
        accessibility_label="Password",
        variant=ComponentVariant(
            component_id="c1",
            variant_properties={"Type": "Password"},
        ),
    )
    layout = render_layout_file(node, feature_name="login", uses_svg=False)[
        "lib/generated/login_layout.dart"
    ]

    assert "obscureText: true" in layout
