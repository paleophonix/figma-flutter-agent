"""Regression tests for bottom-nav, chip-row, bleed-art, and clip repair laws."""

from __future__ import annotations

from figma_flutter_agent.generator.checks.layout import (
    build_responsiveness_report,
    classify_clean_tree_responsive_tier,
)
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.extracted import emit_extracted_widget_code_from_ir
from figma_flutter_agent.generator.layout import render_layout_file, render_node_body
from figma_flutter_agent.generator.layout.cupertino import wrap_scroll_viewport
from figma_flutter_agent.generator.layout.flex_policy.text import text_in_card_metadata_rail
from figma_flutter_agent.generator.layout.widgets.finalize import _finalize_widget
from figma_flutter_agent.generator.layout.widgets.option_chip import (
    try_emit_chip_choice_layout_for_node,
)
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
from figma_flutter_agent.schemas import SizingMode


def _vertical_chip_tile(*, label_top: float = 75.0) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="chip",
        name="Group 6817",
        type=NodeType.STACK,
        sizing=Sizing(width=65.0, height=92.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Rectangle 216",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=65.0, height=65.0),
                style=NodeStyle(background_color="0xFF8E97FD", border_radius=25.0),
                stack_placement=StackPlacement(bottom=27.0, width=65.0, height=65.0),
            ),
            CleanDesignTreeNode(
                id="icon-slot",
                name="Frame",
                type=NodeType.STACK,
                sizing=Sizing(width=25.0, height=25.0),
                stack_placement=StackPlacement(left=20.0, top=20.0, width=25.0, height=25.0),
                children=[
                    CleanDesignTreeNode(
                        id="glyph",
                        name="Vector",
                        type=NodeType.VECTOR,
                        vector_asset_key="assets/icons/chip.svg",
                        sizing=Sizing(width=25.0, height=25.0),
                    ),
                ],
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
    assert "bottom: 0.0" in positioned


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


def test_hero_editorial_cover_paints_before_text() -> None:
    """Cover imagery must paint before title/subtitle overlays inside hero cards."""
    from figma_flutter_agent.generator.layout.widgets.hero import (
        sort_hero_editorial_cover_stack_children,
    )

    hero = CleanDesignTreeNode(
        id="hero",
        name="Hero card",
        type=NodeType.STACK,
        sizing=Sizing(width=373.6, height=233.0),
        children=[
            CleanDesignTreeNode(
                id="lock",
                name="Lock",
                type=NodeType.STACK,
                sizing=Sizing(width=30.0, height=30.0),
                stack_placement=StackPlacement(left=11.5, top=10.0, width=30.0, height=30.0),
            ),
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="The Ocean Moon",
                sizing=Sizing(width=200.0, height=40.0),
                stack_placement=StackPlacement(top=68.0, width=200.0, height=40.0),
            ),
            CleanDesignTreeNode(
                id="cover",
                name="Cover",
                type=NodeType.IMAGE,
                image_asset_key="assets/images/hero.png",
                sizing=Sizing(width=373.6, height=233.0),
                stack_placement=StackPlacement(width=373.6, height=233.0),
            ),
        ],
    )
    ordered = sort_hero_editorial_cover_stack_children(hero, hero.children)
    ids = [child.id for child in ordered]
    assert ids.index("cover") < ids.index("title")


def test_flattened_vector_group_emits_parent_asset() -> None:
    """Composite vector groups must emit the parent SVG instead of empty child glyphs."""
    group = CleanDesignTreeNode(
        id="group",
        name="Icon group",
        type=NodeType.STACK,
        sizing=Sizing(width=18.0, height=22.0),
        vector_asset_key="assets/icons/group_icon.svg",
        vector_svg_path_count=2,
        children=[
            CleanDesignTreeNode(
                id="v1",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=7.0, height=7.0),
                style=NodeStyle(background_color="0xFF98A1BD"),
                stack_placement=StackPlacement(left=11.0, top=0.0, width=7.0, height=7.0),
            ),
            CleanDesignTreeNode(
                id="v2",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=16.4, height=16.2),
                style=NodeStyle(background_color="0xFF98A1BD"),
                stack_placement=StackPlacement(left=0.0, top=5.8, width=16.4, height=16.2),
            ),
        ],
    )
    emitted = render_node_body(group, uses_svg=True, parent_type=NodeType.STACK)
    assert "group_icon.svg" in emitted
    assert "SizedBox.shrink()" not in emitted


def test_nav_icon_glyph_uses_contain_in_tall_slot() -> None:
    """Non-square nav icon slots must not stretch glyphs with BoxFit.fill."""
    from figma_flutter_agent.generator.layout.widgets.svg import _svg_fit_mode

    node = CleanDesignTreeNode(
        id="icon",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=39.0, height=39.0),
        style=NodeStyle(background_color="0xFF98A1BD"),
    )
    assert _svg_fit_mode(node, 39.0, 54.0) == "BoxFit.contain"


def test_materialize_missing_cluster_delegate_files() -> None:
    """Referenced cluster widgets must be emitted even when not in the initial spec batch."""
    from figma_flutter_agent.generator.widget_extractor import (
        materialize_missing_cluster_delegate_files,
    )

    representative = CleanDesignTreeNode(
        id="c6",
        name="Cluster glyph",
        type=NodeType.VECTOR,
        cluster_id="cluster_6",
        vector_asset_key="assets/icons/cluster_6.svg",
        sizing=Sizing(width=6.5, height=11.3),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        sizing=Sizing(width=65.0, height=92.0),
        children=[representative],
    )
    planned = {
        "lib/widgets/chip_row_widget.dart": (
            "import 'package:demo_app/widgets/cluster6_widget.dart';\n"
            "class ChipRowWidget extends StatelessWidget {\n"
            "  Widget build(BuildContext context) => const Cluster6Widget();\n"
            "}\n"
        )
    }
    merged = materialize_missing_cluster_delegate_files(
        planned,
        clean_tree=root,
        cluster_classes={"cluster_6": "Cluster6Widget"},
        uses_svg=True,
        package_name="demo_app",
        use_package_imports=True,
    )
    assert any("cluster6_widget.dart" in path for path in merged)
    assert "Cluster6Widget" in next(iter(merged[path] for path in merged if "cluster6" in path))


def test_vertical_chip_button_splits_icon_surface_band() -> None:
    """Category chip ink must target the icon surface, leaving the label band outside."""
    chip = _vertical_chip_tile()
    emitted = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
    assert "height: 65.0" in emitted
    assert "bottom: 0.0" in emitted
    assert "Align(alignment: Alignment.center" not in emitted


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


def test_no_per_component_scaledown_on_fixed_slots() -> None:
    """Fixed chip and nav slots must clip overflow instead of FittedBox scaleDown."""
    chip = _vertical_chip_tile()
    chip_out = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
    assert "BoxFit.scaleDown" not in chip_out

    nav_column = CleanDesignTreeNode(
        id="col",
        name="Tab column",
        type=NodeType.COLUMN,
        sizing=Sizing(width=34.0, height=54.0),
        children=[
            CleanDesignTreeNode(
                id="icon",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/home.svg",
                sizing=Sizing(width=19.5, height=23.0),
            ),
            CleanDesignTreeNode(
                id="label",
                name="Afsar",
                type=NodeType.TEXT,
                text="Afsar",
                sizing=Sizing(width=34.0, height=15.0),
                style=NodeStyle(font_size=14.0, text_align="CENTER"),
            ),
        ],
    )
    nav_out = render_node_body(nav_column, uses_svg=True, parent_type=NodeType.STACK)
    assert "BoxFit.scaleDown" not in nav_out
    assert "double.infinity" not in nav_out
    assert "width: 34.0" in nav_out


def test_active_nav_pill_splits_surface_band() -> None:
    """Active nav tabs must bind ink to the painted pill, not the full tab stack."""
    tab = CleanDesignTreeNode(
        id="tab",
        name="Group 30",
        type=NodeType.STACK,
        sizing=Sizing(width=46.0, height=66.0),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Rectangle 18",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=46.0, height=46.0),
                style=NodeStyle(background_color="0xFF8E97FD", border_radius=18.0),
                stack_placement=StackPlacement(bottom=20.0, width=46.0, height=46.0),
            ),
            CleanDesignTreeNode(
                id="icon",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/moon.svg",
                sizing=Sizing(width=22.8, height=22.0),
                stack_placement=StackPlacement(left=11.5, top=12.0, width=22.8, height=22.0),
            ),
            CleanDesignTreeNode(
                id="label",
                name="Sleep",
                type=NodeType.TEXT,
                text="Sleep",
                sizing=Sizing(width=37.0, height=15.0),
                style=NodeStyle(font_size=14.0, text_align="LEFT"),
                stack_placement=StackPlacement(left=3.5, top=51.0, width=37.0, height=15.0),
            ),
        ],
    )
    emitted = render_node_body(tab, uses_svg=True, parent_type=NodeType.STACK)
    assert "BoxFit.scaleDown" not in emitted
    assert "height: 46.0" in emitted
    assert "top: 51.0" in emitted
    assert "width: 59" not in emitted


def _nav_tab_glyph_stack(*, label: str = "Music") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="tab",
        name="Group 28",
        type=NodeType.STACK,
        sizing=Sizing(width=39.0, height=54.0),
        children=[
            CleanDesignTreeNode(
                id="icon-group",
                name="Group",
                type=NodeType.STACK,
                sizing=Sizing(width=25.8, height=22.0),
                stack_placement=StackPlacement(left=7.0, width=25.8, height=22.0),
                children=[
                    CleanDesignTreeNode(
                        id="v1",
                        name="Vector",
                        type=NodeType.VECTOR,
                        vector_asset_key="assets/icons/note_a.svg",
                        sizing=Sizing(width=11.8, height=11.5),
                        stack_placement=StackPlacement(
                            horizontal="SCALE",
                            vertical="SCALE",
                            top=10.5,
                            width=11.8,
                            height=11.5,
                        ),
                    ),
                    CleanDesignTreeNode(
                        id="v2-wrap",
                        name="Vector wrap",
                        type=NodeType.STACK,
                        sizing=Sizing(width=15.9, height=19.2),
                        stack_placement=StackPlacement(left=10.0, top=0.0, width=15.9, height=19.2),
                        children=[
                            CleanDesignTreeNode(
                                id="v2",
                                name="Vector",
                                type=NodeType.VECTOR,
                                vector_asset_key="assets/icons/note_b.svg",
                                sizing=Sizing(width=15.9, height=19.2),
                                stack_placement=StackPlacement(width=15.9, height=19.2),
                            ),
                        ],
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="label",
                name=label,
                type=NodeType.TEXT,
                text=label,
                sizing=Sizing(width=39.0, height=15.0),
                style=NodeStyle(font_size=14.0, text_align="CENTER"),
                stack_placement=StackPlacement(top=39.0, width=39.0, height=15.0),
            ),
        ],
    )


def test_flowing_nav_tab_stack_label_uses_bounded_center() -> None:
    """Bottom-nav glyph stacks must center labels in bounded slots, not metadata rails."""
    emitted = render_node_body(_nav_tab_glyph_stack(), uses_svg=True, parent_type=NodeType.STACK)
    assert "double.infinity" not in emitted
    assert "Alignment.centerRight" not in emitted
    assert "width: 39.0" in emitted
    assert "Text('Music'" in emitted


def test_bottom_nav_glyph_stack_skips_chip_choice_and_circle_border() -> None:
    """Compact nav tabs must not collapse into chip_choice or circular icon buttons."""
    tab = CleanDesignTreeNode(
        id="home-tab",
        name="Group 31",
        type=NodeType.STACK,
        sizing=Sizing(width=39.0, height=54.0),
        children=[
            CleanDesignTreeNode(
                id="icon",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/home.svg",
                sizing=Sizing(width=21.5, height=22.0),
                stack_placement=StackPlacement(
                    horizontal="SCALE",
                    vertical="SCALE",
                    left=9.0,
                    width=21.5,
                    height=22.0,
                ),
            ),
            CleanDesignTreeNode(
                id="label",
                name="Home",
                type=NodeType.TEXT,
                text="Home",
                sizing=Sizing(width=39.0, height=15.0),
                style=NodeStyle(font_size=14.0, text_align="LEFT"),
                stack_placement=StackPlacement(top=39.0, width=39.0, height=15.0),
            ),
        ],
    )
    assert try_emit_chip_choice_layout_for_node(tab, IrEmitContext(uses_svg=True)) is None
    emitted = render_node_body(tab, uses_svg=True, parent_type=NodeType.STACK)
    assert "CircleBorder" not in emitted
    assert "Text('Home'" in emitted


def test_stroke_glyph_in_chip_band_skips_circular_clip() -> None:
    """Stroke heart glyphs inside chip icon bands must not get auto circular ClipRRect."""
    frame = CleanDesignTreeNode(
        id="frame",
        name="Frame",
        type=NodeType.STACK,
        sizing=Sizing(width=28.0, height=25.0),
        stack_placement=StackPlacement(left=18.5, top=20.0, width=28.0, height=25.0),
        children=[
            CleanDesignTreeNode(
                id="heart",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/heart.svg",
                sizing=Sizing(width=25.6, height=22.4),
                style=NodeStyle(border_width=2.0),
                stack_placement=StackPlacement(width=25.6, height=22.4),
            ),
        ],
    )
    chip = _vertical_chip_tile()
    chip.children[1].children = [frame]
    emitted = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
    assert "ClipRRect(borderRadius: BorderRadius.circular(14.0)" not in emitted


def test_hero_cta_pill_label_centers_without_metadata_rail() -> None:
    """Hero CTA pill labels must center instead of using card metadata-rail alignment."""
    cta = CleanDesignTreeNode(
        id="cta",
        name="START button",
        type=NodeType.STACK,
        sizing=Sizing(width=70.2, height=35.1),
        stack_placement=StackPlacement(left=151.7, top=177.9, width=70.2, height=35.1),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Rectangle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=70.2, height=35.1),
                style=NodeStyle(background_color="0xFFEBEAEC", border_radius=25.0),
                stack_placement=StackPlacement(width=70.2, height=35.1),
            ),
            CleanDesignTreeNode(
                id="label",
                name="START",
                type=NodeType.TEXT,
                text="START",
                sizing=Sizing(width=41.1, height=14.0),
                style=NodeStyle(font_size=12.0, text_align="LEFT"),
                stack_placement=StackPlacement(left=15.0, top=11.0, width=41.1, height=14.0),
            ),
        ],
    )
    assert not text_in_card_metadata_rail(
        cta.children[1],
        cta,
        parent_type=NodeType.STACK,
    )
    emitted = render_node_body(cta, uses_svg=True, parent_type=NodeType.STACK)
    assert "Alignment.centerRight" not in emitted
    assert "Alignment.center" in emitted


def test_composite_nav_icon_preserves_absolute_slots() -> None:
    """Layered nav icons must keep absolute glyph slots instead of Positioned.fill."""
    emitted = render_node_body(_nav_tab_glyph_stack(label="Music"), uses_svg=True, parent_type=NodeType.STACK)
    assert "Positioned.fill" not in emitted
    assert "left: 10.0" in emitted


def test_static_viewport_wrap_anchors_top_not_center() -> None:
    """Static mode must pin artboard scroll hosts to top-left, not viewport center."""
    wrapped = wrap_scroll_viewport(
        "SingleChildScrollView(child: SizedBox(width: 414.0, height: 896.0))",
        theme_variant="material_3",
        anchor_top=True,
    )
    assert "Center(" not in wrapped
    assert "SingleChildScrollView" in wrapped


def test_static_clean_tree_reports_fixed_tier() -> None:
    """Static responsive mode must not label absolute stacks as scaled."""
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="a",
                name="A",
                type=NodeType.TEXT,
                text="Title",
                stack_placement=StackPlacement(top=66.0, width=200.0, height=30.0),
            ),
            CleanDesignTreeNode(
                id="b",
                name="B",
                type=NodeType.TEXT,
                text="Body",
                stack_placement=StackPlacement(top=111.0, width=300.0, height=44.0),
            ),
            CleanDesignTreeNode(
                id="c",
                name="C",
                type=NodeType.TEXT,
                text="Nav",
                stack_placement=StackPlacement(top=806.0, width=39.0, height=54.0),
            ),
        ],
    )
    report = build_responsiveness_report(screen, responsive_enabled=False)
    assert report["tier"] == "fixed"
    assert classify_clean_tree_responsive_tier(screen, responsive_enabled=False) == "fixed"


def _painted_status_chip(*, chip_id: str, label: str, width: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=chip_id,
        name="Background+Border",
        type=NodeType.ROW,
        padding=Padding(top=7.0, bottom=9.0, left=16.0, right=16.0),
        sizing=Sizing(width=width, height=39.0, width_mode=SizingMode.FIXED),
        style=NodeStyle(
            background_color="0xFFEEF9F0",
            border_radius=20.0,
            has_stroke=True,
            border_color="0xFFC4E9CB",
            border_width=1.0,
        ),
        alignment={"main": "center", "cross": "center"},
        children=[
            CleanDesignTreeNode(
                id=f"{chip_id}-text",
                name=label,
                type=NodeType.TEXT,
                text=label,
                sizing=Sizing(width=max(20.0, width - 32.0), height=21.0),
                style=NodeStyle(font_size=14.0, text_align="CENTER"),
            ),
        ],
    )


def test_overflowing_painted_chip_strip_emits_horizontal_scroll() -> None:
    """Chip strips wider than the parent band must scroll horizontally."""
    parent = CleanDesignTreeNode(
        id="parent",
        name="Parent",
        type=NodeType.COLUMN,
        sizing=Sizing(width=317.0, width_mode=SizingMode.FILL),
        children=[],
    )
    strip = CleanDesignTreeNode(
        id="strip",
        name="Chip strip",
        type=NodeType.ROW,
        spacing=8.0,
        sizing=Sizing(width=522.0, height=39.0, width_mode=SizingMode.FIXED),
        children=[
            _painted_status_chip(chip_id="c1", label="Новый", width=91.0),
            _painted_status_chip(chip_id="c2", label="На сборке", width=104.0),
            _painted_status_chip(chip_id="c3", label="Собран", width=90.0),
            _painted_status_chip(chip_id="c4", label="В пути", width=90.0),
        ],
    )
    emitted = render_node_body(
        strip,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
        parent_node=parent,
    )
    assert "scrollDirection: Axis.horizontal" in emitted
    assert "mainAxisSize: MainAxisSize.min" in emitted


def test_painted_pill_chip_label_avoids_ellipsis_clip() -> None:
    """Painted pill interiors must show full chip labels without ellipsis."""
    chip = _painted_status_chip(chip_id="pill", label="Новый", width=91.0)
    emitted = render_node_body(chip, uses_svg=False, parent_type=NodeType.ROW)
    assert "TextOverflow.ellipsis" not in emitted
    assert "Новый" in emitted


def test_static_form_page_avoids_per_panel_expanded_scroll() -> None:
    """Static tier must not split form cards into nested Expanded scroll pockets."""
    header = CleanDesignTreeNode(
        id="header",
        name="Header",
        type=NodeType.STACK,
        sizing=Sizing(width=357.0, height=84.0),
        stack_placement=StackPlacement(top=0.0, width=357.0, height=84.0),
        children=[],
    )
    card_a = CleanDesignTreeNode(
        id="card-a",
        name="Card A",
        type=NodeType.COLUMN,
        sizing=Sizing(width=357.0, height=180.0, height_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(top=104.0, width=357.0, height=180.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=28.0),
        children=[
            CleanDesignTreeNode(
                id="title-a",
                name="Title",
                type=NodeType.TEXT,
                text="Section A",
            ),
        ],
    )
    card_b = CleanDesignTreeNode(
        id="card-b",
        name="Card B",
        type=NodeType.COLUMN,
        sizing=Sizing(width=357.0, height=220.0, height_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(top=300.0, width=357.0, height=220.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=28.0),
        children=[
            CleanDesignTreeNode(
                id="title-b",
                name="Title",
                type=NodeType.TEXT,
                text="Section B",
            ),
        ],
    )
    action = CleanDesignTreeNode(
        id="action",
        name="Action",
        type=NodeType.BUTTON,
        sizing=Sizing(width=357.0, height=52.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=52.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=357.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[header, card_a, card_b, action],
    )
    layout = render_layout_file(
        screen,
        skip_layout_reconcile=True,
        feature_name="static_form_scroll",
        uses_svg=False,
        responsive_enabled=False,
    )["lib/generated/static_form_scroll_layout.dart"]
    compact = layout.replace("\n", "")
    assert "Expanded(child: SingleChildScrollView" not in compact


def test_label_value_summary_row_expands_value_slot() -> None:
    """Checkout detail rows must flex the value column instead of fixed ellipsis slots."""
    label_stack = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.STACK,
        sizing=Sizing(width=90.0, height=21.0, width_mode=SizingMode.FIXED),
        children=[
            CleanDesignTreeNode(
                id="label-text",
                name="Дата и время",
                type=NodeType.TEXT,
                text="Дата и время",
                stack_placement=StackPlacement(bottom=0.9, width=106.0, height=21.0),
            ),
        ],
    )
    value_stack = CleanDesignTreeNode(
        id="value",
        name="Value",
        type=NodeType.STACK,
        sizing=Sizing(width=103.0, height=21.0, width_mode=SizingMode.FIXED),
        children=[
            CleanDesignTreeNode(
                id="value-text",
                name="Сегодня, 13:00",
                type=NodeType.TEXT,
                text="Сегодня, 13:00",
                stack_placement=StackPlacement(left=0.0, right=0.0, bottom=0.9, height=21.0),
            ),
        ],
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Row",
        type=NodeType.ROW,
        alignment={"main": "spaceBetween", "cross": "center"},
        sizing=Sizing(width=317.0, height=29.0),
        children=[label_stack, value_stack],
    )
    emitted = render_node_body(row, uses_svg=False)
    assert "Expanded(child: Align(alignment: Alignment.centerRight" in emitted
    assert "TextOverflow.ellipsis" not in emitted
    assert "Сегодня, 13:00" in emitted


def test_tall_multiline_input_shell_uses_top_aligned_padding() -> None:
    """Tall comment shells must not inherit single-line bottom padding starvation."""
    hint = CleanDesignTreeNode(
        id="hint",
        name="Hint",
        type=NodeType.TEXT,
        text="Позвонить за 5 минут до доставки.",
        stack_placement=StackPlacement(left=16.0, top=15.0, width=250.0, height=21.0),
        style=NodeStyle(font_size=14.0),
    )
    surface = CleanDesignTreeNode(
        id="surface",
        name="Surface",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=317.0, height=116.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
    )
    field_host = CleanDesignTreeNode(
        id="field",
        name="Comment field",
        type=NodeType.INPUT,
        sizing=Sizing(width=317.0, height=116.0, min_height=104.0),
        padding=Padding(left=16.0, right=16.0, bottom=16.0),
        children=[surface, hint],
    )
    emitted = render_node_body(field_host, uses_svg=False)
    assert "minLines: 3" in emitted
    assert "contentPadding: EdgeInsets.fromLTRB(16.0, 15.0, 16.0, 16.0)" in emitted
    assert ", 79.0)" not in emitted
