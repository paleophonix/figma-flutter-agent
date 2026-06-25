"""Regression tests for payment-history layout laws (nav bar, tabs, card copy)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.text_metrics import (
    positioned_text_width_with_metric_slack,
)
from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    stack_child_should_emit_positioned,
)
from figma_flutter_agent.generator.layout.flex_policy.text import text_in_card_metadata_rail
from figma_flutter_agent.generator.layout.widgets.position import _ensure_positioned_stack_bounds
from figma_flutter_agent.generator.layout.widgets.text import _positioned_fields
from figma_flutter_agent.parser.interaction import (
    button_compiles_body_as_flex_row,
    button_has_icon_label_inline_affordance,
    button_hosts_top_navigation_bar,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    ShadowEffect,
    Sizing,
    StackPlacement,
)


def _top_navigation_bar() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="389:41",
        name="Navigation Bar / Black",
        type=NodeType.BUTTON,
        sizing=Sizing(width=375.0, height=53.0),
        variant=ComponentVariant(component_id="100:281", component_name="Navigation Bar / Black"),
        children=[
            CleanDesignTreeNode(
                id="I389:41;100:266",
                name="Title",
                type=NodeType.TEXT,
                text="Payment history",
                sizing=Sizing(width=168.0, height=28.0),
                style=NodeStyle(font_size=20.0, font_weight="w600", text_align="LEFT"),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    horizontal="CENTER",
                    vertical="CENTER",
                    left=103.5,
                    top=12.5,
                    right=151.0,
                    width=168.0,
                    height=28.0,
                ),
            ),
            CleanDesignTreeNode(
                id="I389:41;100:278",
                name="Back",
                type=NodeType.STACK,
                sizing=Sizing(width=16.0, height=16.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    vertical="SCALE",
                    left=24.0,
                    top=31.0,
                    right=335.0,
                    bottom=6.0,
                    width=16.0,
                    height=16.0,
                ),
                children=[
                    CleanDesignTreeNode(
                        id="I389:41;100:278;54:21611",
                        name="Path",
                        type=NodeType.VECTOR,
                        vector_asset_key="assets/icons/back.svg",
                        sizing=Sizing(width=8.7, height=16.0),
                    )
                ],
            ),
        ],
    )


def _segmented_tab_chip(*, label: str, active: bool) -> CleanDesignTreeNode:
    fill = "0xFF3629B7" if active else "0xFFF2F1F9"
    text_color = "0xFFFFFFFF" if active else "0xFF343434"
    return CleanDesignTreeNode(
        id="295:37388",
        name="Tab",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=44.0),
        variant=ComponentVariant(component_id="386:4087", component_name="Tab / Active"),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Rectangle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=100.0, height=44.0),
                style=NodeStyle(background_color=fill, border_radius=15.0),
                stack_placement=StackPlacement(width=100.0, height=44.0),
            ),
            CleanDesignTreeNode(
                id="label",
                name=label,
                type=NodeType.TEXT,
                text=label,
                sizing=Sizing(width=59.0, height=24.0),
                style=NodeStyle(
                    font_size=16.0,
                    font_weight="w500",
                    text_align="CENTER",
                    text_color=text_color,
                ),
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    vertical="CENTER",
                    top=10.0,
                    bottom=10.0,
                    width=59.0,
                    height=24.0,
                ),
            ),
        ],
    )


def test_top_navigation_bar_must_not_compile_as_inline_icon_row() -> None:
    """Law: navigation_bar_must_not_lower_to_inline_icon_row."""
    nav = _top_navigation_bar()
    assert button_hosts_top_navigation_bar(nav)
    assert not button_has_icon_label_inline_affordance(nav)
    assert not button_compiles_body_as_flex_row(nav)


def test_flex_row_button_children_must_not_emit_positioned() -> None:
    """Law: positioned_child_requires_stack_parent."""
    plus = CleanDesignTreeNode(
        id="plus",
        name="Plus",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/plus.svg",
        sizing=Sizing(width=16.0, height=16.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=16.0, height=16.0),
    )
    label = CleanDesignTreeNode(
        id="label",
        name="Add new card",
        type=NodeType.TEXT,
        text="Add new card",
        stack_placement=StackPlacement(left=20.0, top=0.0, width=120.0, height=16.0),
    )
    button = CleanDesignTreeNode(
        id="add",
        name="Add new card",
        type=NodeType.BUTTON,
        sizing=Sizing(width=200.0, height=40.0),
        children=[plus, label],
    )
    assert button_compiles_body_as_flex_row(button)
    for child in button.children:
        assert not stack_child_should_emit_positioned(
            child,
            parent_type=NodeType.BUTTON,
            parent_node=button,
        )


def test_top_navigation_bar_children_keep_positioned_under_stack() -> None:
    """Top nav bars compile as overlay stacks with positioned slots."""
    nav = _top_navigation_bar()
    title = nav.children[0]
    assert stack_child_should_emit_positioned(
        title,
        parent_type=NodeType.BUTTON,
        parent_node=nav,
    )


def test_top_navigation_bar_emits_stack_not_row_with_positioned_children() -> None:
    """Law: navigation_bar_must_keep_absolute_stack_geometry."""
    emitted = render_node_body(_top_navigation_bar(), uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "Row(mainAxisAlignment" not in compact
    assert "Stack(" in compact
    assert "Positioned(" in compact


def test_segmented_category_tab_chip_is_not_metadata_rail() -> None:
    """Law: centered pill labels must not use card metadata-rail alignment."""
    chip = _segmented_tab_chip(label="Electric", active=True)
    label = chip.children[1]
    assert not text_in_card_metadata_rail(label, chip, parent_type=NodeType.STACK)


def test_segmented_tab_label_centers_without_metadata_rail_wrap() -> None:
    """Law: chip_tab_label_center_align."""
    emitted = render_node_body(
        _segmented_tab_chip(label="Electric", active=True),
        uses_svg=True,
        parent_type=NodeType.STACK,
    )
    assert "Alignment.centerRight" not in emitted
    assert "textAlign: TextAlign.center" in emitted


def test_absolute_text_slot_width_includes_metric_slack() -> None:
    """Law: absolute_text_slot_width_must_cover_glyph_bounds."""
    node = CleanDesignTreeNode(
        id="389:77",
        name="30/10/2019",
        type=NodeType.TEXT,
        text="30/10/2019",
        sizing=Sizing(width=62.0, height=16.0),
        style=NodeStyle(font_size=12.0, font_weight="w600"),
        stack_placement=StackPlacement(left=245.0, top=16.0, width=62.0, height=16.0),
    )
    placement = node.stack_placement
    assert placement is not None
    fields = _positioned_fields(placement)
    _ensure_positioned_stack_bounds(fields, node, placement)
    joined = ", ".join(fields)
    assert f"width: {positioned_text_width_with_metric_slack(62.0)}" in joined


def test_center_pinned_nav_title_emits_left_right_without_metric_slack() -> None:
    """Law: center_pinned_text_must_emit_left_right_not_fixed_width."""
    nav = _top_navigation_bar()
    title = nav.children[0]
    placement = title.stack_placement
    assert placement is not None
    fields = _positioned_fields(placement)
    _ensure_positioned_stack_bounds(fields, title, placement)
    joined = ", ".join(fields)
    assert "left: 103.5" in joined
    assert "right: 151.0" in joined
    assert "width:" not in joined


def test_top_navigation_bar_title_uses_shared_vertical_center_lane() -> None:
    """Law: navigation_bar_title_and_leading_affordance_share_vertical_center_lane."""
    nav = _top_navigation_bar()
    title = nav.children[0]
    placement = title.stack_placement
    assert placement is not None
    fields = _positioned_fields(placement)
    _ensure_positioned_stack_bounds(fields, title, placement)
    from figma_flutter_agent.generator.layout.widgets.position import (
        top_navigation_bar_child_vertical_fields,
    )

    nav_vertical = top_navigation_bar_child_vertical_fields(
        nav,
        child_height=float(placement.height or 28.0),
    )
    assert nav_vertical is not None
    assert nav_vertical[0] == "top: 12.5"


def test_top_navigation_bar_emits_centered_title_pins() -> None:
    """Center-pinned nav titles render with horizontal stretch and centered label."""
    emitted = render_node_body(_top_navigation_bar(), uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "left: 103.5" in compact
    assert "right: 151.0" in compact
    assert "width: 178.1" not in compact
    assert "SizedBox(width: double.infinity, child: Center(child:" in compact


def _peek_tab_chip() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="389:138",
        name="Tab / Disable",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=44.0),
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(
            horizontal="LEFT",
            left=360.0,
            top=117.0,
            right=-85.0,
            width=100.0,
            height=44.0,
        ),
        children=_segmented_tab_chip(label="Electric", active=False).children,
    )


def test_peek_tab_strip_preserves_intrinsic_width_at_artboard_edge() -> None:
    """Law: artboard_overflow_child_must_clip_not_shrink_intrinsic_width."""
    from figma_flutter_agent.parser.layout import clamp_stack_child_placement_to_parent

    placement = _peek_tab_chip().stack_placement
    assert placement is not None
    clamped = clamp_stack_child_placement_to_parent(placement, 375.0)
    assert clamped.width == 100.0
    assert clamped.left == 360.0


def test_peek_tab_emits_full_chip_width_not_squeezed_label() -> None:
    """Peek tabs keep chip geometry; artboard clipping handles the visible slice."""
    emitted = render_node_body(_peek_tab_chip(), uses_svg=True, parent_type=NodeType.STACK)
    assert "width: 15.0" not in emitted.replace(" ", "")
    assert "Container(width: 100.0" in emitted.replace("\n", "")


def _list_card_shell() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="389:75",
        name="Card",
        type=NodeType.CARD,
        sizing=Sizing(width=327.0, height=88.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius=15.0,
            elevation=7.5,
            effects=[
                ShadowEffect(offset_y=4.0, blur=30.0, color="0x123629B7"),
            ],
        ),
        children=[],
    )


def test_list_card_with_figma_effects_emits_box_decoration_not_material_card() -> None:
    """Law: card_with_figma_effects_must_emit_box_decoration_not_material_elevation."""
    emitted = render_node_body(_list_card_shell(), uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "Container(decoration: BoxDecoration(" in compact
    assert "boxShadow:" in compact
    assert "Card(elevation:" not in compact


def test_apply_ir_guards_preserves_peek_tab_placement() -> None:
    """IR viewport guard must not shift right-edge peek tabs before emit."""
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.generator.ir.validate import apply_ir_guards

    peek = _peek_tab_chip()
    root = CleanDesignTreeNode(
        id="291:469",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[peek],
    )
    ir = default_screen_ir(root)
    guarded_root = apply_ir_guards(ir, root, preserve_placement=False)
    guarded_tab = guarded_root.children[0]
    assert guarded_tab.stack_placement is not None
    assert guarded_tab.stack_placement.left == 360.0
    assert guarded_tab.stack_placement.width == 100.0


def test_overlay_container_card_styled_primitive_skips_theme_material_shell() -> None:
    """Overlay card groups must not receive theme Material tint shells."""
    from figma_flutter_agent.generator.ir.context import IrEmitContext
    from figma_flutter_agent.generator.ir.fidelity.styled_emit import emit_styled_primitive
    from figma_flutter_agent.schemas import WidgetIrKind, WidgetIrNode

    shell = _list_card_shell().model_copy(
        update={
            "stack_placement": StackPlacement(
                left=0.0,
                bottom=0.0,
                width=327.0,
                height=88.0,
            ),
        }
    )
    label = CleanDesignTreeNode(
        id="label",
        name="October",
        type=NodeType.TEXT,
        text="October",
        sizing=Sizing(width=96.0, height=24.0),
        stack_placement=StackPlacement(left=16.0, top=16.0, width=96.0, height=24.0),
    )
    group = CleanDesignTreeNode(
        id="card-group",
        name="Card",
        type=NodeType.CARD,
        sizing=Sizing(width=327.0, height=88.0),
        children=[shell, label],
    )
    ir = WidgetIrNode(figma_id="card-group", kind=WidgetIrKind.CONTAINER_CARD)
    ctx = IrEmitContext(uses_svg=True, responsive_enabled=False)
    emitted = emit_styled_primitive(ir, clean=group, ctx=ctx)
    compact = emitted.replace("\n", "")
    assert "surfaceContainerLow" not in compact
    assert "Container(decoration: BoxDecoration(" in compact
