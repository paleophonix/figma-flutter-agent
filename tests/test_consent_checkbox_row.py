"""Consent label + checkbox row merge and render."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.parser.interaction import _stack_spans_primary_button_and_footer_link
from figma_flutter_agent.parser.layout import (
    reconcile_consent_checkbox_rows_in_tree,
    reconcile_stack_placement_top_from_edges,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_infer_top_when_top_missing_and_bottom_present() -> None:
    placement = StackPlacement(vertical="TOP", bottom=20.0, height=10.0)
    result = reconcile_stack_placement_top_from_edges(placement, parent_height=100.0)
    assert result.top is not None
    assert abs(float(result.top) - 70.0) <= 1.0


def test_tall_screen_stack_is_not_cta_footer_button_stack() -> None:
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Create your account",
                style=NodeStyle(font_size=30.0),
            ),
            CleanDesignTreeNode(
                id="cta",
                name="GET STARTED",
                type=NodeType.TEXT,
                text="GET STARTED",
            ),
            CleanDesignTreeNode(
                id="policy",
                name="Policy",
                type=NodeType.TEXT,
                text="Privacy Policy",
            ),
        ],
    )
    text_nodes = [c for c in screen.children if c.type == NodeType.TEXT]
    assert not _stack_spans_primary_button_and_footer_link(screen, text_nodes=text_nodes)


def test_consent_row_merges_label_and_checkbox() -> None:
    label = CleanDesignTreeNode(
        id="1:label",
        name="Policy",
        type=NodeType.TEXT,
        text="I have read the Privacy Policy",
        stack_placement=StackPlacement(left=20.0, top=650.0, width=220.0, height=20.0),
    )
    box = CleanDesignTreeNode(
        id="1:cb",
        name="Checkbox",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=24.2, height=24.2),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFA1A4B2",
            border_width=2.0,
            border_radius=4.0,
        ),
        stack_placement=StackPlacement(left=360.0, top=650.0, width=24.2, height=24.2),
    )
    stack = CleanDesignTreeNode(
        id="1:form",
        name="Form",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[label, box],
    )
    merged = reconcile_consent_checkbox_rows_in_tree(stack)
    assert len(merged.children) == 1
    row = merged.children[0]
    assert row.name == "ConsentRow"
    assert row.stack_placement is not None
    assert row.stack_placement.width is not None
    assert float(row.stack_placement.width) > 300.0


def test_consent_row_renders_expanded_text_and_checkbox() -> None:
    label = CleanDesignTreeNode(
        id="1:label",
        name="Policy",
        type=NodeType.TEXT,
        text="I have read the Privacy Policy",
        stack_placement=StackPlacement(left=20.0, top=650.0, width=220.0, height=20.0),
    )
    box = CleanDesignTreeNode(
        id="1:cb",
        name="Checkbox",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=24.2, height=24.2),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFA1A4B2",
            border_width=2.0,
            border_radius=4.0,
        ),
        stack_placement=StackPlacement(left=360.0, top=650.0, width=24.2, height=24.2),
    )
    row = CleanDesignTreeNode(
        id="1:cb-consent-row",
        name="ConsentRow",
        type=NodeType.STACK,
        sizing=Sizing(width=364.0, height=24.2),
        stack_placement=StackPlacement(left=20.0, top=650.0, width=364.0, height=24.2),
        children=[label, box],
    )
    body = render_node_body(row, uses_svg=False)
    assert "Expanded(child:" in body
    assert "Checkbox(" in body
    assert "onChanged:" in body
    assert "Privacy Policy" in body


def test_headline_not_centered_like_cta_on_tall_screen() -> None:
    title = CleanDesignTreeNode(
        id="1:3642",
        name="Title",
        type=NodeType.TEXT,
        text="Create your account",
        style=NodeStyle(font_size=30.0),
        stack_placement=StackPlacement(left=20.0, top=89.5, width=374.0, height=40.0),
    )
    screen = CleanDesignTreeNode(
        id="1:screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[title],
    )
    layout = render_layout_file(screen, feature_name="signup_title", uses_svg=False)[
        "lib/generated/signup_title_layout.dart"
    ]
    assert "top: 89.5" in layout or "top: 90.0" in layout
    assert "Positioned(left: 0.0, top: 0.0, width:" not in layout
