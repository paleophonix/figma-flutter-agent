"""Regression tests for mobile nav + tab switcher emit laws (my_orders class)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.generator.layout.flex_policy.row import (
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


def test_trailing_action_nav_title_uses_screen_center_lane() -> None:
    nav = _trailing_action_nav_bar()
    emitted = render_node_body(nav, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "SizedBox(width: double.infinity, child: Center(child:" in compact
    assert "right:45.0" in compact.replace(" ", "") or "right: 45.0" in compact


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
    """Law: tab_bar_items_must_preserve_distinct_label_cells_and_indicator_ownership."""
    emitted = render_node_body(_tab_switcher_stack(), uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "Row(crossAxisAlignment: CrossAxisAlignment.center" in compact
    assert "Expanded(child:" in compact
    assert "Ongoing" in compact and "History" in compact
