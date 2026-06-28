"""Tests for parse-time stack paint ordering."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.parser.stack_paint import (
    apply_stack_paint_order_to_clean_tree,
    sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_sort_absolute_stack_children_puts_large_backdrop_first_at_root() -> None:
    backdrop = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.IMAGE,
        image_asset_key="assets/bg.png",
        sizing=Sizing(width=400.0, height=800.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=400.0, height=800.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        stack_placement=StackPlacement(left=20.0, top=100.0, width=120.0, height=44.0),
    )
    ordered = sort_absolute_stack_children(
        [button, backdrop],
        is_layout_root=True,
    )
    assert [child.id for child in ordered] == ["bg", "btn"]


def test_sort_absolute_stack_children_puts_content_sheet_before_foreground_tiles() -> None:
    content_sheet = CleanDesignTreeNode(
        id="sheet",
        name="Rectangle 33",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=375.0, height=750.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius_corners={
                "topLeft": 30.0,
                "topRight": 30.0,
                "bottomRight": 0.0,
                "bottomLeft": 0.0,
            },
        ),
        stack_placement=StackPlacement(left=0.0, top=130.0, width=375.0, height=750.0),
    )
    pruned_tile = CleanDesignTreeNode(
        id="tile-pruned",
        name="Category",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        component_ref="169:21549",
        render_boundary=True,
        stack_placement=StackPlacement(left=140.0, top=407.0, width=100.0, height=100.0),
    )
    full_tile = CleanDesignTreeNode(
        id="tile-full",
        name="Category",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        component_ref="169:21549",
        stack_placement=StackPlacement(left=140.0, top=407.0, width=100.0, height=100.0),
        children=[
            CleanDesignTreeNode(
                id="shell",
                name="Card",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=100.0, height=100.0),
            )
        ],
    )
    ordered = sort_absolute_stack_children(
        [pruned_tile, content_sheet, full_tile],
        is_layout_root=True,
    )
    assert [child.id for child in ordered][0] == "sheet"
    assert ordered[-1].id == "tile-full"


def test_sort_absolute_stack_children_keeps_bottom_checkbox_at_layout_root() -> None:
    checkbox = CleanDesignTreeNode(
        id="cb",
        name="Rectangle 213",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=24.2, height=24.2),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFA1A4B2",
            border_width=2.0,
            border_radius=4.0,
        ),
        stack_placement=StackPlacement(left=360.0, top=700.0, width=24.2, height=24.2),
    )
    ordered = sort_absolute_stack_children([checkbox], is_layout_root=True)
    assert [child.id for child in ordered] == ["cb"]


def test_apply_stack_paint_order_on_clean_tree_root() -> None:
    backdrop = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.VECTOR,
        vector_asset_key="assets/bg.svg",
        sizing=Sizing(width=400.0, height=800.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=400.0, height=800.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        stack_placement=StackPlacement(left=20.0, top=100.0, width=120.0, height=44.0),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[button, backdrop],
    )
    ordered_root = apply_stack_paint_order_to_clean_tree(root)
    assert [child.id for child in ordered_root.children] == ["bg", "btn"]


def test_validate_aligns_ir_stack_children_to_clean_tree_order() -> None:
    backdrop = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.VECTOR,
        vector_asset_key="assets/bg.svg",
        sizing=Sizing(width=400.0, height=800.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=400.0, height=800.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        stack_placement=StackPlacement(left=20.0, top=100.0, width=120.0, height=44.0),
    )
    root = apply_stack_paint_order_to_clean_tree(
        CleanDesignTreeNode(
            id="root",
            name="Screen",
            type=NodeType.STACK,
            sizing=Sizing(width=414.0, height=896.0),
            children=[backdrop, button],
        ),
    )
    screen_ir = default_screen_ir(root)
    screen_ir.root.children = list(reversed(screen_ir.root.children))
    validate_screen_ir(screen_ir, root)
    assert [child.figma_id for child in screen_ir.root.children] == ["bg", "btn"]


def test_sort_mixed_stack_applies_z_order_to_positioned_only() -> None:
    flow_text = CleanDesignTreeNode(
        id="flow",
        name="Title",
        type=NodeType.TEXT,
        text="Hello",
        sizing=Sizing(width=200.0, height=24.0),
    )
    backdrop = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.IMAGE,
        image_asset_key="assets/bg.png",
        sizing=Sizing(width=400.0, height=800.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=400.0, height=800.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        stack_placement=StackPlacement(left=20.0, top=100.0, width=120.0, height=44.0),
    )
    ordered = sort_absolute_stack_children(
        [button, backdrop, flow_text],
        is_layout_root=True,
    )
    assert [child.id for child in ordered] == ["flow", "bg", "btn"]


def test_sort_puts_full_bleed_vector_stack_backdrop_first() -> None:
    """Flattened full-screen vector illustrations paint under foreground panels."""
    star = CleanDesignTreeNode(
        id="star",
        name="Starfield",
        type=NodeType.STACK,
        vector_asset_key="assets/illustrations/starfield.svg",
        render_boundary=True,
        sizing=Sizing(width=376.0, height=812.0),
        stack_placement=StackPlacement(left=-1.0, width=376.0, height=812.0),
    )
    content_sheet = CleanDesignTreeNode(
        id="sheet",
        name="Rectangle 33",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=375.0, height=591.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius_corners={
                "topLeft": 30.0,
                "topRight": 30.0,
                "bottomRight": 0.0,
                "bottomLeft": 0.0,
            },
        ),
        stack_placement=StackPlacement(left=0.0, top=221.0, width=375.0, height=591.0),
    )
    ordered = sort_absolute_stack_children(
        [content_sheet, star],
        is_layout_root=True,
    )
    assert [child.id for child in ordered] == ["star", "sheet"]


def test_docked_full_width_footer_row_paints_above_scroll_content() -> None:
    from figma_flutter_agent.parser.stack_paint import (
        _is_bottom_nav_interactive,
        sort_absolute_stack_children,
    )

    scroll = CleanDesignTreeNode(
        id="scroll",
        name="Scroll",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=1448.0),
        stack_placement=StackPlacement(top=120.0, width=390.0, height=1448.0),
    )
    tabs = [
        CleanDesignTreeNode(
            id=f"tab-{index}",
            name="Icon button",
            type=NodeType.BUTTON,
            sizing=Sizing(width=40.0, height=40.0),
        )
        for index in range(5)
    ]
    footer = CleanDesignTreeNode(
        id="footer",
        name="Footer",
        type=NodeType.ROW,
        sizing=Sizing(width=390.0, height=106.0),
        stack_placement=StackPlacement(vertical="BOTTOM", top=738.0, width=390.0, height=106.0),
        children=tabs,
    )
    assert _is_bottom_nav_interactive(
        footer,
        viewport_width=390.0,
        viewport_height=844.0,
    )
    ordered = sort_absolute_stack_children([footer, scroll], is_layout_root=True)
    assert ordered[-1].id == "footer"


def test_viewport_chrome_paints_above_content_sheet() -> None:
    """Home indicator and status chrome must paint above growable content cards."""
    content_sheet = CleanDesignTreeNode(
        id="sheet",
        name="Rectangle 33",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=375.0, height=591.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius_corners={
                "topLeft": 30.0,
                "topRight": 30.0,
                "bottomRight": 0.0,
                "bottomLeft": 0.0,
            },
        ),
        stack_placement=StackPlacement(left=0.0, top=221.0, width=375.0, height=591.0),
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", top=778.0, width=375.0, height=34.0),
        children=[],
    )
    ordered = sort_absolute_stack_children(
        [home, content_sheet],
        is_layout_root=True,
    )
    assert ordered[-1].id == "home"
