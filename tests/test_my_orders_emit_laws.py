"""Regression tests for mobile nav + tab switcher emit laws (my_orders class)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.generator.layout.flex_policy.row import (
    layout_fact_bounded_inline_summary_row,
    layout_fact_stack_tab_switcher_host,
)
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    stack_child_should_emit_positioned,
)
from figma_flutter_agent.parser.interaction import (
    button_compiles_body_as_flex_row,
    button_has_icon_label_inline_affordance,
    button_hosts_top_navigation_bar,
)
from figma_flutter_agent.parser.layout import refine_text_stack_placement
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def _trailing_action_nav_bar() -> CleanDesignTreeNode:
    """Leading back + screen-centered title + trailing more affordance."""
    return CleanDesignTreeNode(
        id="133:660",
        name="Top",
        type=NodeType.BUTTON,
        sizing=Sizing(width=327.0, height=45.0),
        children=[
            CleanDesignTreeNode(
                id="133:661",
                name="Back",
                type=NodeType.STACK,
                sizing=Sizing(width=45.0, height=45.0),
                stack_placement=StackPlacement(left=0.0, width=45.0, height=45.0),
                children=[
                    CleanDesignTreeNode(
                        id="133:663",
                        name="Ellipse",
                        type=NodeType.VECTOR,
                        vector_asset_key="assets/icons/ellipse_back.svg",
                        sizing=Sizing(width=45.0, height=45.0),
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="133:665",
                name="More",
                type=NodeType.STACK,
                sizing=Sizing(width=45.0, height=45.0),
                stack_placement=StackPlacement(left=282.0, width=45.0, height=45.0),
                children=[
                    CleanDesignTreeNode(
                        id="133:666",
                        name="Ellipse",
                        type=NodeType.VECTOR,
                        vector_asset_key="assets/icons/ellipse_more.svg",
                        sizing=Sizing(width=45.0, height=45.0),
                    ),
                    CleanDesignTreeNode(
                        id="133:667",
                        name="More",
                        type=NodeType.STACK,
                        sizing=Sizing(width=16.0, height=2.0),
                        vector_asset_key="assets/icons/more_kebab.svg",
                        vector_svg_path_count=3,
                        stack_placement=StackPlacement(
                            left=14.4,
                            top=21.3,
                            width=16.0,
                            height=2.0,
                        ),
                        children=[],
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="133:671",
                name="My Orders",
                type=NodeType.TEXT,
                text="My Orders",
                sizing=Sizing(width=82.0, height=22.0),
                style=NodeStyle(font_size=17.0, text_align="LEFT"),
                stack_placement=StackPlacement(left=61.0, top=12.0, width=82.0, height=22.0),
            ),
        ],
    )


def _tab_switcher_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="142:2",
        name="Tab",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=33.0),
        stack_placement=StackPlacement(top=119.0, width=375.0, height=33.0),
        children=[
            CleanDesignTreeNode(
                id="142:8",
                name="Line 5",
                type=NodeType.VECTOR,
                sizing=Sizing(width=146.0, height=2.0),
                stack_placement=StackPlacement(
                    left=229.0,
                    bottom=0.0,
                    width=146.0,
                    height=2.0,
                ),
            ),
            CleanDesignTreeNode(
                id="142:7",
                name="Line 4",
                type=NodeType.VECTOR,
                sizing=Sizing(width=375.0, height=1.0),
                stack_placement=StackPlacement(
                    left=0.0,
                    bottom=0.0,
                    width=375.0,
                    height=1.0,
                ),
            ),
            CleanDesignTreeNode(
                id="142:4",
                name="Ongoing",
                type=NodeType.TEXT,
                text="Ongoing",
                sizing=Sizing(width=57.0, height=17.0),
                style=NodeStyle(font_size=14.0, text_align="CENTER"),
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    left=68.0,
                    bottom=16.0,
                    width=57.0,
                    height=17.0,
                ),
            ),
            CleanDesignTreeNode(
                id="142:6",
                name="History",
                type=NodeType.TEXT,
                text="History",
                sizing=Sizing(width=51.0, height=17.0),
                style=NodeStyle(font_size=14.0, font_weight="w700", text_align="CENTER"),
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    left=252.0,
                    bottom=16.0,
                    width=51.0,
                    height=17.0,
                ),
            ),
        ],
    )


def test_trailing_action_nav_bar_detected_and_not_flex_row() -> None:
    """Law: mobile_nav_bar_actions_must_preserve_leading_title_trailing_slots."""
    nav = _trailing_action_nav_bar()
    assert button_hosts_top_navigation_bar(nav)
    assert not button_has_icon_label_inline_affordance(nav)
    assert not button_compiles_body_as_flex_row(nav)


def test_trailing_action_nav_bar_emits_stack_without_positioned_under_row() -> None:
    """Law: positioned_nodes_must_have_stack_ancestor_contract."""
    emitted = render_node_body(
        _trailing_action_nav_bar(),
        uses_svg=True,
        parent_type=NodeType.STACK,
    )
    compact = emitted.replace("\n", "")
    assert "Stack(clipBehavior" in compact
    assert "Row(mainAxisAlignment" not in compact
    assert "left:282.0" in compact.replace(" ", "") or "left: 282.0" in compact
    assert "SizedBox(width:45.0,height:45.0,child:Positioned" not in compact.replace(" ", "")


def test_trailing_action_nav_title_preserves_leading_alignment() -> None:
    """Law: nav_title_must_preserve_figma_horizontal_alignment_in_affordance_lane."""
    nav = _trailing_action_nav_bar()
    emitted = render_node_body(nav, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "SizedBox(width: double.infinity, child: Center(child:" not in compact
    assert "left:61.0" in compact.replace(" ", "") or "left: 61.0" in compact


def test_refine_text_stack_placement_preserves_distinct_tab_slots() -> None:
    """Center-aligned tab labels keep geometry left when they own a horizontal slot."""
    placement = StackPlacement(
        horizontal="LEFT",
        left=68.0,
        bottom=16.0,
        width=57.0,
        height=17.0,
    )
    refined = refine_text_stack_placement(
        NodeType.TEXT,
        NodeStyle(text_align="CENTER"),
        NodeType.STACK,
        placement,
    )
    assert refined is not None
    assert refined.left == 68.0
    assert refined.horizontal != "LEFT_RIGHT" or refined.right != 0.0 or refined.left != 0.0


def test_tab_switcher_stack_detected() -> None:
    assert layout_fact_stack_tab_switcher_host(_tab_switcher_stack())


def test_tab_switcher_children_do_not_emit_positioned() -> None:
    tab = _tab_switcher_stack()
    for child in tab.children:
        assert not stack_child_should_emit_positioned(
            child,
            parent_type=NodeType.STACK,
            parent_node=tab,
        )


def test_trailing_action_nav_bar_emits_atomic_more_icon() -> None:
    """Law: circular_icon_buttons_must_emit_as_atomic_bounded_controls."""
    emitted = render_node_body(
        _trailing_action_nav_bar(),
        uses_svg=True,
        parent_type=NodeType.STACK,
    )
    assert "more_kebab.svg" in emitted


def test_tab_switcher_emits_row_with_expanded_cells() -> None:
    """Law: tab_switcher_emit_must_preserve_indicator_and_baseline_divider."""
    emitted = render_node_body(_tab_switcher_stack(), uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "Stack(clipBehavior: Clip.none" in compact
    assert "Positioned(left: 0.0, right: 0.0, top: 0.0, bottom: 0.0" in compact
    assert "Row(crossAxisAlignment: CrossAxisAlignment.center" in compact
    assert "Expanded(child:" in compact
    assert "Ongoing" in compact and "History" in compact
    row_idx = compact.find("Positioned(left: 0.0, right: 0.0, top: 0.0, bottom: 0.0")
    bottom_idx = compact.find("bottom: 0.0")
    assert row_idx >= 0 and bottom_idx >= 0
    assert row_idx < bottom_idx
    assert "Positioned(top: -1.0" not in compact or bottom_idx < compact.find("Positioned(top: -1.0")


def test_composite_icon_button_interaction_preserves_glyph_stack() -> None:
    """Law: circular_icon_button_must_emit_full_composite_glyph_stack."""
    nav = _trailing_action_nav_bar()
    more = next(child for child in nav.children if child.id == "133:665")
    with patch(
        "figma_flutter_agent.generator.layout.widgets.emit.stack.stack_interaction_kind",
        side_effect=lambda node: "button" if node.id == "133:665" else None,
    ):
        emitted = render_node_body(
            more,
            uses_svg=True,
            parent_type=NodeType.BUTTON,
            parent_node=nav,
        )
    assert "InkWell(" in emitted
    assert "more_kebab.svg" in emitted
    assert "ellipse_more.svg" in emitted
    ink_idx = emitted.find("InkWell(")
    assert ink_idx >= 0
    assert "more_kebab.svg" in emitted[ink_idx:]
    assert "ellipse_more.svg" in emitted[ink_idx:]


def test_processed_more_stack_kebab_survives_button_wrap() -> None:
    """Law: circular_icon_button_must_emit_full_composite_glyph_stack (fixture tree)."""
    processed_path = (
        Path(__file__).resolve().parents[1]
        / ".debug/screen/limbo/my_orders_02/processed.json"
    )
    if not processed_path.is_file():
        return
    payload = json.loads(processed_path.read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(payload["cleanTree"])

    def find(nid: str, node: CleanDesignTreeNode = root) -> CleanDesignTreeNode | None:
        if node.id == nid:
            return node
        for child in node.children:
            found = find(nid, child)
            if found is not None:
                return found
        return None

    nav = find("133:660")
    more = find("133:665")
    assert nav is not None and more is not None
    with patch(
        "figma_flutter_agent.generator.layout.widgets.emit.stack.stack_interaction_kind",
        side_effect=lambda node: "button" if node.id == "133:665" else None,
    ):
        emitted = render_node_body(
            more,
            uses_svg=True,
            parent_type=NodeType.BUTTON,
            parent_node=nav,
        )
    ink_idx = emitted.find("InkWell(")
    assert ink_idx >= 0
    tail = emitted[ink_idx:]
    assert "more_133_667.svg" in tail or "more_kebab.svg" in tail
    assert "ellipse_1294_133_666.svg" in tail


def _bounded_inline_summary_row() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="149:217",
        name="Frame 3137",
        type=NodeType.ROW,
        spacing=14.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=216.0, height=17.0),
        children=[
            CleanDesignTreeNode(
                id="142:29",
                name="$35.25",
                type=NodeType.TEXT,
                text="$35.25",
                sizing=Sizing(width=43.0, height=17.0),
            ),
            CleanDesignTreeNode(
                id="148:0",
                name="Divider",
                type=NodeType.VECTOR,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=0.0, height=16.0),
            ),
            CleanDesignTreeNode(
                id="133:492",
                name="Metadata",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=145.0, height=14.0),
                children=[
                    CleanDesignTreeNode(
                        id="133:493",
                        name="Date",
                        type=NodeType.TEXT,
                        text="20 Jun 2024",
                        sizing=Sizing(width=80.0, height=14.0),
                    ),
                ],
            ),
        ],
    )


def test_bounded_inline_summary_row_detected() -> None:
    assert layout_fact_bounded_inline_summary_row(_bounded_inline_summary_row())


def test_bounded_inline_summary_row_wraps_metadata_segment() -> None:
    """Law: metadata_row_fixed_width_must_not_sum_exact_intrinsics_without_slack."""
    emitted = render_node_body(
        _bounded_inline_summary_row(),
        uses_svg=True,
        parent_type=NodeType.COLUMN,
    )
    compact = emitted.replace("\n", "")
    assert "flex: 1" in compact and "20 Jun 2024" in compact
