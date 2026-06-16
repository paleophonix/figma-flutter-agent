"""Regression tests for bottom-nav, chip-row, bleed-art, and clip repair laws."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.extracted import emit_extracted_widget_code_from_ir
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets.finalize import _finalize_widget
from figma_flutter_agent.generator.layout.widgets.text import _apply_stack_position
from figma_flutter_agent.generator.planned.reconcile.class_inspect import (
    _is_shrink_only_widget_source,
)
from figma_flutter_agent.parser.interaction import stack_interaction_kind
from figma_flutter_agent.parser.interaction.icons import (
    layout_fact_stack_vertical_icon_label_chip_tile,
)
from figma_flutter_agent.parser.stack_paint import sort_absolute_stack_children
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _vertical_chip_tile(*, label_top: float = 75.0) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="chip",
        name="Filter chip",
        type=NodeType.STACK,
        sizing=Sizing(width=65.0, height=92.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Icon surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=65.0, height=65.0),
                style=NodeStyle(background_color="0xFF586894", border_radius=25.0),
                stack_placement=StackPlacement(bottom=27.0, width=65.0, height=65.0),
            ),
            CleanDesignTreeNode(
                id="label",
                name="All",
                type=NodeType.TEXT,
                text="All",
                sizing=Sizing(width=19.0, height=17.0),
                style=NodeStyle(font_size=16.0),
                stack_placement=StackPlacement(horizontal="LEFT_RIGHT", top=label_top, width=19.0),
            ),
        ],
    )


def test_bottom_nav_background_only_gets_ignore_pointer() -> None:
    """Passive bar fill stays non-interactive; tab icons remain hittable."""
    nav_shell = CleanDesignTreeNode(
        id="nav-shell",
        name="Bottom bar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=414.0, height=112.0),
        style=NodeStyle(background_color="0xFF03174D"),
        stack_placement=StackPlacement(left=0.0, top=784.0, width=414.0, height=112.0),
    )
    nav_icon = CleanDesignTreeNode(
        id="nav-icon",
        name="Meditate",
        type=NodeType.STACK,
        sizing=Sizing(width=58.0, height=54.0),
        stack_placement=StackPlacement(left=175.0, top=806.0, width=58.0, height=54.0),
        children=[],
    )
    shell_out = _finalize_widget(nav_shell, "Container(color: Colors.red)", parent_type=None)
    icon_out = _finalize_widget(nav_icon, "const Text('Meditate')", parent_type=None)
    assert "IgnorePointer" in shell_out
    assert "IgnorePointer" not in icon_out


def test_render_boundary_bleed_art_preserves_negative_left() -> None:
    """Render-boundary header art must not be clamped to the artboard at emit time."""
    parent = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
    )
    union = CleanDesignTreeNode(
        id="union",
        name="Union",
        type=NodeType.STACK,
        sizing=Sizing(width=503.6, height=275.2),
        render_boundary=True,
        stack_placement=StackPlacement(left=-49.5, top=-20.0, width=503.6, height=275.2),
    )
    positioned = _apply_stack_position(
        union,
        "const Placeholder()",
        parent_type=NodeType.STACK,
        parent_node=parent,
    )
    assert "left: -49.5" in positioned
    assert "width: 503.6" in positioned


def test_vertical_icon_label_chip_tile_fact_and_label_anchor() -> None:
    """Chip labels in the lower band must not be vertically centered across the full tile."""
    tile = _vertical_chip_tile()
    assert layout_fact_stack_vertical_icon_label_chip_tile(tile)
    assert stack_interaction_kind(tile) == "button"
    from figma_flutter_agent.generator.layout.widgets.text import (
        _position_button_stack_label,
    )

    label = tile.children[1]
    placement = label.stack_placement
    assert placement is not None
    positioned = _position_button_stack_label(
        "const Text('All')",
        text_node=label,
        parent_node=tile,
        placement=placement,
    )
    assert "Align(alignment: Alignment.center" not in positioned
    assert "top: 75.0" in positioned


def test_overlap_content_paints_above_bottom_nav_background() -> None:
    """Tiles that intersect the nav band must paint above the bar fill but under tab icons."""
    nav_shell = CleanDesignTreeNode(
        id="nav-shell",
        name="Bottom bar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=414.0, height=112.0),
        style=NodeStyle(background_color="0xFF03174D"),
        stack_placement=StackPlacement(left=0.0, top=784.0, width=414.0, height=112.0),
    )
    tile = CleanDesignTreeNode(
        id="tile",
        name="Tile",
        type=NodeType.STACK,
        sizing=Sizing(width=177.0, height=122.9),
        stack_placement=StackPlacement(left=20.0, top=758.0, width=177.0, height=122.9),
    )
    nav_icon = CleanDesignTreeNode(
        id="nav-icon",
        name="Meditate",
        type=NodeType.STACK,
        sizing=Sizing(width=58.0, height=54.0),
        stack_placement=StackPlacement(left=175.0, top=806.0, width=58.0, height=54.0),
    )
    ordered = sort_absolute_stack_children(
        [nav_icon, tile, nav_shell],
        is_layout_root=True,
    )
    ids = [child.id for child in ordered]
    assert ids.index("nav-shell") < ids.index("tile") < ids.index("nav-icon")


def test_repaint_boundary_shrink_stub_is_detected() -> None:
    """Shrink wrapped in RepaintBoundary must still count as an empty widget stub."""
    stub = (
        "class TabWidget extends StatelessWidget {\n"
        "  const TabWidget({super.key});\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        "    return RepaintBoundary(child: const SizedBox.shrink());\n"
        "  }\n"
        "}\n"
    )
    assert _is_shrink_only_widget_source(stub)


def test_extracted_widget_repaint_boundary_shrink_refreshes() -> None:
    """Materializer must replace RepaintBoundary shrink stubs when paint remains."""
    icon = CleanDesignTreeNode(
        id="2",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/meditate.svg",
        sizing=Sizing(width=18.0, height=22.0),
    )
    label = CleanDesignTreeNode(
        id="3",
        name="Meditate",
        type=NodeType.TEXT,
        text="Meditate",
        sizing=Sizing(width=58.0, height=15.0),
        style=NodeStyle(font_size=14.0),
        stack_placement=StackPlacement(top=39.0, width=58.0, height=15.0),
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Tab",
        type=NodeType.STACK,
        sizing=Sizing(width=58.0, height=54.0),
        children=[icon, label],
    )
    widget_ir = WidgetIrNode(figma_id="1", kind=WidgetIrKind.STACK, children=[])
    ctx = IrEmitContext(uses_svg=True, responsive_enabled=False, is_layout_root=True)
    code = emit_extracted_widget_code_from_ir(
        widget_ir,
        clean_tree=root,
        widget_name="TabWidget",
        ctx=ctx,
    )
    assert "SizedBox.shrink()" not in code
    assert "meditate.svg" in code


def test_rounded_cover_card_emits_clip_rrect() -> None:
    """Hero cards with cover imagery must clip to the rounded surface radius."""
    hero = CleanDesignTreeNode(
        id="hero",
        name="Hero card",
        type=NodeType.STACK,
        sizing=Sizing(width=373.6, height=233.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Rectangle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=373.6, height=233.0),
                style=NodeStyle(background_color="0xFF8E97FD", border_radius=10.0),
                stack_placement=StackPlacement(width=373.6, height=233.0),
            ),
            CleanDesignTreeNode(
                id="photo",
                name="Photo",
                type=NodeType.IMAGE,
                image_asset_key="assets/images/hero.png",
                sizing=Sizing(width=456.5, height=290.2),
                stack_placement=StackPlacement(width=456.5, height=290.2),
            ),
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="The Ocean Moon",
                sizing=Sizing(width=200.0, height=40.0),
                style=NodeStyle(font_size=36.0),
                stack_placement=StackPlacement(top=68.0, width=200.0, height=40.0),
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[hero],
    )
    layout = render_layout_file(
        screen,
        feature_name="hero_clip",
        uses_svg=True,
    )["lib/generated/hero_clip_layout.dart"]
    assert "ClipRRect(borderRadius: BorderRadius.circular(10.0)" in layout


def test_small_vector_badge_emits_clip_rrect() -> None:
    """Outward vector bleed inside small badges must be clipped to badge bounds."""
    badge = CleanDesignTreeNode(
        id="badge",
        name="Lock badge",
        type=NodeType.STACK,
        sizing=Sizing(width=30.0, height=30.0),
        children=[
            CleanDesignTreeNode(
                id="ellipse",
                name="Ellipse",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/ellipse.svg",
                sizing=Sizing(width=30.0, height=30.0),
                style=NodeStyle(
                    render_bounds_expand=Padding(top=1.0, bottom=1.0, left=1.0, right=1.0),
                ),
                stack_placement=StackPlacement(width=30.0, height=30.0),
            ),
        ],
    )
    out = _finalize_widget(badge, "Stack(children: [const Placeholder()])", parent_type=None)
    assert "ClipRRect(borderRadius: BorderRadius.circular(15.0)" in out
