"""Tests for Figma → Flutter flex wrap policy."""

from __future__ import annotations

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.flex_policy import (
    FlexWrapKind,
    apply_flex_wrap_to_widget,
    relax_row_cross_stretch_when_unbounded,
    resolve_cross_axis_alignment,
    resolve_flex_wrap,
    row_hosts_equal_metric_cards,
    stack_has_non_sequential_raster_overlay,
    stack_should_flow_as_column,
    wrap_column_child_width_fill,
)
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_row_fill_child_gets_expanded() -> None:
    node = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hi",
        sizing=Sizing(width_mode=SizingMode.FILL),
    )
    assert resolve_flex_wrap(parent_type=NodeType.ROW, node=node) == FlexWrapKind.EXPANDED


def test_row_fixed_text_gets_flexible_loose() -> None:
    node = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hi",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=120.0),
    )
    assert resolve_flex_wrap(parent_type=NodeType.ROW, node=node) == FlexWrapKind.FLEXIBLE_LOOSE


def test_row_fixed_text_renders_flexible_in_layout() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Hello",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=100.0),
    )
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width=400.0),
        children=[child],
    )
    layout = render_layout_file(row, feature_name="flex_row", uses_svg=False)[
        "lib/generated/flex_row_layout.dart"
    ]
    assert "Flexible(fit: FlexFit.loose" in layout


def test_column_stack_child_gets_bounded_sized_box() -> None:
    back = CleanDesignTreeNode(
        id="42:3733",
        name="arrow-narrow-left",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=24.0, height=24.0),
        children=[],
    )
    column = CleanDesignTreeNode(
        id="42:3215",
        name="Content",
        type=NodeType.COLUMN,
        sizing=Sizing(width=327.0, height=511.0),
        children=[back],
    )
    layout = render_layout_file(column, feature_name="content_col", uses_svg=False)[
        "lib/generated/content_col_layout.dart"
    ]
    assert "SizedBox(width: 24.0, height: 24.0, child: Stack(" in layout


def test_apply_flex_wrap_expanded_expression() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="X",
        type=NodeType.TEXT,
        text="A",
        sizing=Sizing(width_mode=SizingMode.FILL),
    )
    wrapped = apply_flex_wrap_to_widget(
        "Text('A')",
        parent_type=NodeType.ROW,
        node=node,
    )
    assert wrapped == "Expanded(child: Text('A'))"


def test_bottom_anchored_fixed_height_stack_under_column_uses_sized_box_not_expanded() -> None:
    """BottomAnchoredStackColumnBoundLaw: finite logo stacks must not flex-expand."""
    logo = CleanDesignTreeNode(
        id="logo",
        name="Logo",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=101.0,
            height=18.4,
        ),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=18.4, height=18.4),
                stack_placement=StackPlacement(
                    vertical="BOTTOM",
                    bottom=0.0,
                    width=18.4,
                    height=18.4,
                ),
            ),
        ],
    )
    headline = CleanDesignTreeNode(
        id="headline",
        name="Headline",
        type=NodeType.COLUMN,
        spacing=32.0,
        sizing=Sizing(width=327.0, height=163.4),
        alignment=Alignment(main="center", cross="stretch"),
        children=[logo],
    )
    stack_expr = "Stack(clipBehavior: Clip.none, children: [])"
    wrapped = apply_flex_wrap_to_widget(
        stack_expr,
        parent_type=NodeType.COLUMN,
        node=logo,
        parent_node=headline,
    )
    assert "Expanded(" not in wrapped
    assert "width: 101.0" in wrapped
    assert "height: 18.4" in wrapped
    assert "Stack(" in wrapped


def test_bottom_anchored_fill_height_stack_under_column_still_expands() -> None:
    """Growable bottom-anchored panels without finite height keep Expanded under Column."""
    panel = CleanDesignTreeNode(
        id="panel",
        name="Panel",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FILL, height_mode=SizingMode.FILL),
        children=[
            CleanDesignTreeNode(
                id="cta",
                name="CTA",
                type=NodeType.BUTTON,
                sizing=Sizing(width=327.0, height=48.0),
                stack_placement=StackPlacement(vertical="BOTTOM", bottom=0.0, height=48.0),
            ),
        ],
    )
    wrapped = apply_flex_wrap_to_widget(
        "Stack(clipBehavior: Clip.none, children: [])",
        parent_type=NodeType.COLUMN,
        node=panel,
    )
    assert wrapped.startswith("Expanded(child: Stack(")


def test_column_width_fill_row_with_height_gets_bounded_sized_box() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL, height=48.0),
        children=[],
    )
    wrapped = apply_flex_wrap_to_widget(
        "Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [])",
        parent_type=NodeType.COLUMN,
        node=row,
    )
    assert "SizedBox(width: double.infinity, height: 48.0, child: Row(" in wrapped


def test_row_cross_stretch_relaxes_under_parent_row() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Inner",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL),
        children=[],
    )
    cross = resolve_cross_axis_alignment(
        row,
        parent_type=NodeType.ROW,
        cross="stretch",
    )
    assert cross == "CrossAxisAlignment.start"


def test_wrap_child_row_cross_stretch_relaxes_under_unbounded_wrap() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="ChipRow",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL),
        children=[],
    )
    cross = resolve_cross_axis_alignment(
        row,
        parent_type=NodeType.WRAP,
        cross="stretch",
    )
    assert cross == "CrossAxisAlignment.start"


def test_row_cross_stretch_kept_under_column_with_pixel_height() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Bar",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL, height=48.0),
        children=[],
    )
    cross = resolve_cross_axis_alignment(
        row,
        parent_type=NodeType.COLUMN,
        cross="stretch",
    )
    assert cross == "CrossAxisAlignment.stretch"


def test_row_cross_stretch_relaxed_for_title_toolbar() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Header",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Title",
                type=NodeType.COLUMN,
                children=[
                    CleanDesignTreeNode(
                        id="3",
                        name="Label",
                        type=NodeType.TEXT,
                        text="Личные данные",
                    )
                ],
            )
        ],
    )
    cross = resolve_cross_axis_alignment(
        row,
        parent_type=NodeType.COLUMN,
        cross="stretch",
    )
    assert cross == "CrossAxisAlignment.start"


def test_form_field_group_omits_fixed_height_on_width_fill() -> None:
    field = CleanDesignTreeNode(
        id="1",
        name="Field",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, height=84.0),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Label",
                type=NodeType.TEXT,
                text="ФИО",
            ),
            CleanDesignTreeNode(
                id="3",
                name="Input",
                type=NodeType.INPUT,
                sizing=Sizing(width=317.0, height=52.0),
            ),
        ],
    )
    wrapped = wrap_column_child_width_fill("Column(children: [])", field)
    assert "height: 84.0" not in wrapped
    assert wrapped.startswith("SizedBox(width: double.infinity, child:")


def test_expanded_column_coerces_cross_stretch_at_wrap_time() -> None:
    column = CleanDesignTreeNode(
        id="1",
        name="Labels",
        type=NodeType.COLUMN,
        alignment=Alignment(cross="center"),
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0),
        children=[],
    )
    wrapped = apply_flex_wrap_to_widget(
        "Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [])",
        parent_type=NodeType.ROW,
        node=column,
    )
    assert wrapped.startswith("Expanded(child: Column(")
    assert "crossAxisAlignment: CrossAxisAlignment.stretch" in wrapped


def test_fill_width_column_under_row_stretches_despite_center_cross() -> None:
    column = CleanDesignTreeNode(
        id="1",
        name="Labels",
        type=NodeType.COLUMN,
        alignment=Alignment(cross="center"),
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=112.0),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Caption",
                type=NodeType.TEXT,
                text="Line one\nLine two",
                sizing=Sizing(width_mode=SizingMode.FILL, width=221.0),
            ),
            CleanDesignTreeNode(
                id="3",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=52.0),
            ),
        ],
    )
    cross = resolve_cross_axis_alignment(
        column,
        parent_type=NodeType.ROW,
        cross=column.alignment.cross,
    )
    assert cross == "CrossAxisAlignment.stretch"


def test_column_with_cross_stretch_expands_under_row() -> None:
    title = CleanDesignTreeNode(
        id="2",
        name="Title",
        type=NodeType.TEXT,
        text="Hello",
        sizing=Sizing(width_mode=SizingMode.FILL),
    )
    column = CleanDesignTreeNode(
        id="1",
        name="Labels",
        type=NodeType.COLUMN,
        alignment=Alignment(cross="stretch"),
        children=[title],
    )
    assert resolve_flex_wrap(parent_type=NodeType.ROW, node=column) == FlexWrapKind.EXPANDED


def test_nested_row_with_flexible_child_expands_under_parent_row() -> None:
    label = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Title",
        sizing=Sizing(width_mode=SizingMode.FIXED, width=120.0),
    )
    inner = CleanDesignTreeNode(
        id="1",
        name="Inner",
        type=NodeType.ROW,
        children=[label],
    )
    assert resolve_flex_wrap(parent_type=NodeType.ROW, node=inner) == FlexWrapKind.EXPANDED
    wrapped = apply_flex_wrap_to_widget(
        "Row(children: [])",
        parent_type=NodeType.ROW,
        node=inner,
    )
    assert wrapped.startswith("Expanded(child: Row(")


def test_column_width_fill_row_without_height_relaxes_cross_stretch() -> None:
    row = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        alignment=Alignment(cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL),
        children=[],
    )
    wrapped = apply_flex_wrap_to_widget(
        "Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [])",
        parent_type=NodeType.COLUMN,
        node=row,
    )
    assert "CrossAxisAlignment.stretch" not in wrapped
    assert "SizedBox(width: double.infinity, child: Row(" in wrapped


def test_wrap_column_child_width_fill_is_shared_helper() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, height=12.0),
    )
    assert wrap_column_child_width_fill("Row(children: [])", node).startswith(
        "SizedBox(width: double.infinity, height: 12.0"
    )


def test_row_fill_width_and_height_does_not_wrap_expanded_in_sized_box() -> None:
    """ROW child with FILL on both axes must not become SizedBox → Expanded."""
    from figma_flutter_agent.generator.layout.widgets import _wrap_sizing

    node = CleanDesignTreeNode(
        id="611:1338",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FILL,
            width=336.5,
            height=56.0,
        ),
    )
    wrapped = _wrap_sizing(
        node,
        "Semantics(label: 'Save', child: Text('Save'))",
        parent_type=NodeType.ROW,
    )
    assert "SizedBox(height: double.infinity, child: Expanded" not in wrapped
    assert wrapped.startswith("Expanded(")


def test_relax_row_cross_stretch_preserves_nested_column_stretch() -> None:
    """Width-fill Row wrappers must not clobber nested Column cross-axis stretch."""
    row = (
        "Row(mainAxisAlignment: MainAxisAlignment.start, "
        "crossAxisAlignment: CrossAxisAlignment.stretch, "
        "children: [Expanded(child: Column("
        "crossAxisAlignment: CrossAxisAlignment.stretch, children: [])])]"
    )
    relaxed = relax_row_cross_stretch_when_unbounded(row, node_type=NodeType.ROW)
    assert relaxed.startswith(
        "Row(mainAxisAlignment: MainAxisAlignment.start, "
        "crossAxisAlignment: CrossAxisAlignment.start, "
    )
    assert "Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch" in relaxed


def test_stack_title_subtitle_block_flows_as_column() -> None:
    stack = CleanDesignTreeNode(
        id="text-block",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FILL, width=233.0, height=45.0),
        children=[
            CleanDesignTreeNode(
                id="title-col",
                name="Container",
                type=NodeType.COLUMN,
                stack_placement=StackPlacement(top=0.0, height=22.0),
                children=[
                    CleanDesignTreeNode(
                        id="title",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Адреса доставки",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="sub-col",
                name="Container",
                type=NodeType.COLUMN,
                stack_placement=StackPlacement(top=24.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="sub",
                        name="Subtitle",
                        type=NodeType.TEXT,
                        text="2 сохраненных адреса",
                    )
                ],
            ),
        ],
    )
    assert stack_should_flow_as_column(stack)


def test_stack_should_flow_as_column_for_bottom_nav_glyph_tab() -> None:
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_tab_glyph_column,
    )

    tab = CleanDesignTreeNode(
        id="1:tab",
        name="Group 31",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=39.0,
            height=54.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:icon",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=21.5, height=22.0),
                vector_asset_key="assets/icons/nav_home.svg",
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Home",
                type=NodeType.TEXT,
                text="Home",
                sizing=Sizing(width=39.0, height=15.0),
                style=NodeStyle(font_size=10.0),
            ),
        ],
    )
    assert layout_fact_stack_bottom_nav_tab_glyph_column(tab)
    assert stack_should_flow_as_column(tab)


def test_fixed_width_nav_tabs_are_not_equal_metric_cards() -> None:
    """Bottom-nav tab columns share paint but use fixed width + vertical fill."""
    tab = CleanDesignTreeNode(
        id="1:tab",
        name="Link",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FILL,
            width=80.0,
            height=49.0,
        ),
        style=NodeStyle(background_color="0xFFDCFCE7"),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Главная",
                type=NodeType.TEXT,
                text="Главная",
            )
        ],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        children=[tab, tab],
    )
    assert row_hosts_equal_metric_cards(row) is False
    assert (
        resolve_flex_wrap(parent_type=NodeType.ROW, node=tab, parent_node=row) == FlexWrapKind.NONE
    )


def test_fill_width_metric_cards_expand_even_with_vertical_fill() -> None:
    card = CleanDesignTreeNode(
        id="1:card",
        name="Background",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FILL,
            width=97.7,
            height=71.0,
        ),
        style=NodeStyle(background_color="0xFFF6F6F2"),
        children=[
            CleanDesignTreeNode(
                id="1:value",
                name="15%",
                type=NodeType.TEXT,
                text="15%",
            )
        ],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Container",
        type=NodeType.ROW,
        children=[card, card, card],
    )
    assert row_hosts_equal_metric_cards(row) is True
    assert (
        resolve_flex_wrap(parent_type=NodeType.ROW, node=card, parent_node=row)
        == FlexWrapKind.EXPANDED
    )


def test_centered_glyph_badge_skips_flex_wrap_under_row() -> None:
    text = CleanDesignTreeNode(
        id="1:glyph",
        name="И",
        type=NodeType.TEXT,
        text="И",
        style=NodeStyle(text_align="CENTER", font_size=28.0),
    )
    avatar = CleanDesignTreeNode(
        id="1:avatar",
        name="Background",
        type=NodeType.ROW,
        sizing=Sizing(width=64.0, height=64.0),
        style=NodeStyle(background_color="0xFFEEF9F0"),
        children=[text],
    )
    header = CleanDesignTreeNode(
        id="1:header",
        name="Header",
        type=NodeType.ROW,
        children=[avatar],
    )
    assert (
        resolve_flex_wrap(
            parent_type=NodeType.ROW,
            node=avatar,
            parent_node=header,
        )
        == FlexWrapKind.NONE
    )
    body = render_node_body(avatar, uses_svg=False, parent_type=NodeType.ROW)
    assert "Flexible(" not in body
    assert "SizedBox(width: 64.0, height: 64.0, child: Flexible" not in body


def test_viewport_chrome_band_skips_vertical_center_left_wrap() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_flow_child_horizontal_wrap,
        stack_flow_child_vertical_extent_wrap,
    )

    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(
            left=0.0,
            top=778.0,
            width=375.0,
            height=34.0,
            vertical="BOTTOM",
        ),
        children=[],
    )
    inner = "const SizedBox.shrink()"
    wrapped = stack_flow_child_horizontal_wrap(home, inner)
    assert "bottomCenter" in wrapped or "topCenter" in wrapped
    final = stack_flow_child_vertical_extent_wrap(home, wrapped)
    assert "Alignment.centerLeft" not in final


def test_home_indicator_does_not_trigger_pin_bottom_chrome() -> None:
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        _stack_has_bottom_anchored_child,
    )

    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[
            CleanDesignTreeNode(
                id="content",
                name="Content",
                type=NodeType.COLUMN,
                sizing=Sizing(width=375.0, height=700.0),
            ),
            home,
        ],
    )
    assert not _stack_has_bottom_anchored_child(screen)


def test_space_between_footer_column_stretches_in_phone_shell() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_should_stretch_for_footer_pin,
    )

    footer = CleanDesignTreeNode(
        id="footer",
        name="Footer",
        type=NodeType.TEXT,
        text="Don't have an account? Sign Up",
    )
    column = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        alignment=Alignment(main="spaceBetween"),
        sizing=Sizing(width=327.0, height=600.0),
        children=[
            CleanDesignTreeNode(
                id="form",
                name="Form",
                type=NodeType.COLUMN,
                children=[],
            ),
            footer,
        ],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        children=[column],
    )
    assert column_should_stretch_for_footer_pin(
        column,
        parent_node=screen,
        scroll_content_root=False,
    )


def test_phone_shell_detects_status_bar_without_vertical_placement() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        _stack_is_phone_shell_layout,
        stack_child_is_growable_panel,
    )

    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(width=375.0, height=44.0),
        children=[],
    )
    content = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        alignment=Alignment(main="spaceBetween"),
        sizing=Sizing(width=375.0, height=710.0),
        children=[
            CleanDesignTreeNode(
                id="form",
                name="Form",
                type=NodeType.COLUMN,
                children=[],
            ),
            CleanDesignTreeNode(
                id="footer",
                name="Footer",
                type=NodeType.ROW,
                children=[],
            ),
        ],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[status, content, home],
    )
    growable = sum(1 for child in screen.children if stack_child_is_growable_panel(child))
    assert growable == 1
    assert _stack_is_phone_shell_layout(screen, growable_panels=growable)


def test_phone_shell_body_column_stretches_without_footer_link_heuristic() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_should_stretch_for_footer_pin,
    )

    content = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        alignment=Alignment(main="spaceBetween"),
        sizing=Sizing(width=375.0, height=710.0),
        children=[
            CleanDesignTreeNode(id="form", name="Form", type=NodeType.COLUMN, children=[]),
            CleanDesignTreeNode(
                id="footer",
                name="Footer",
                type=NodeType.TEXT,
                text="Don\u2019t have an account?",
            ),
        ],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[
            CleanDesignTreeNode(
                id="status",
                name="Native / Status Bar",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=44.0),
                stack_placement=StackPlacement(width=375.0, height=44.0),
                children=[],
            ),
            content,
            CleanDesignTreeNode(
                id="home",
                name="Native / Home Indicator",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=34.0),
                stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
                children=[],
            ),
        ],
    )
    assert column_should_stretch_for_footer_pin(
        content,
        parent_node=screen,
        scroll_content_root=False,
    )


def test_native_chrome_vertical_fill_emits_expanded_body() -> None:
    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(width=375.0, height=44.0),
        children=[],
    )
    content = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        alignment=Alignment(main="spaceBetween", cross="stretch"),
        sizing=Sizing(width=375.0, height=710.0, height_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(top=68.0, bottom=34.0, width=375.0, height=710.0),
        children=[
            CleanDesignTreeNode(
                id="form",
                name="Form",
                type=NodeType.COLUMN,
                sizing=Sizing(width=327.0, height=600.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="footer",
                name="Footer",
                type=NodeType.ROW,
                sizing=Sizing(width=327.0, height=17.0),
                children=[],
            ),
        ],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", top=778.0, width=375.0, height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Login Version 1",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[status, content, home],
    )
    layout = render_layout_file(
        screen,
        skip_layout_reconcile=True,
        feature_name="native_chrome_shell",
        uses_svg=False,
    )["lib/generated/native_chrome_shell_layout.dart"]
    assert "mainAxisSize: MainAxisSize.max" in layout
    assert "Expanded(child:" in layout
    assert "MainAxisAlignment.spaceBetween" in layout


def test_phone_shell_static_viewport_law_skips_outer_scroll_wrap() -> None:
    """PhoneShellStaticViewportLaw: static mode must not wrap phone shells in outer scroll."""
    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(width=375.0, height=44.0),
        children=[],
    )
    content = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        alignment=Alignment(main="spaceBetween", cross="stretch"),
        sizing=Sizing(width=375.0, height=710.0, height_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(top=68.0, bottom=34.0, width=375.0, height=710.0),
        children=[
            CleanDesignTreeNode(
                id="form",
                name="Form",
                type=NodeType.COLUMN,
                sizing=Sizing(width=327.0, height=600.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="footer",
                name="Footer",
                type=NodeType.ROW,
                sizing=Sizing(width=327.0, height=17.0),
                children=[],
            ),
        ],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", top=778.0, width=375.0, height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Login Version 1",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[status, content, home],
    )
    layout = render_layout_file(
        screen,
        skip_layout_reconcile=True,
        feature_name="phone_shell_static",
        uses_svg=False,
        responsive_enabled=False,
    )["lib/generated/phone_shell_static_layout.dart"]
    assert "_artboardPreviewWidth" in layout
    assert "LayoutBuilder" in layout
    assert "Expanded(child:" not in layout
    assert "SizedBox(height: 24.0" in layout
    assert "SingleChildScrollView(child: SizedBox(width: 375.0, height: 812.0" not in layout


def test_decomposed_column_phone_shell_expands_content() -> None:
    from figma_flutter_agent.generator.layout.file_methods import (
        LayoutMethod,
        compose_decomposed_root_widget,
    )
    from figma_flutter_agent.schemas import Alignment, SizingMode, StackPlacement

    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(width=375.0, height=44.0),
        children=[],
    )
    content = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        alignment=Alignment(main="spaceBetween", cross="stretch"),
        sizing=Sizing(width=375.0, height=710.0, height_mode=SizingMode.FIXED),
        children=[
            CleanDesignTreeNode(id="form", name="Form", type=NodeType.COLUMN, children=[]),
            CleanDesignTreeNode(
                id="footer",
                name="Footer",
                type=NodeType.TEXT,
                text="Don't have an account? Sign Up",
            ),
        ],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[status, content, home],
    )
    methods = [
        LayoutMethod(name="_buildNativeStatusBar", node=status),
        LayoutMethod(name="_buildContent", node=content),
        LayoutMethod(name="_buildNativeHomeIndicator", node=home),
    ]
    layout = compose_decomposed_root_widget(
        screen,
        methods,
        responsive_enabled=True,
    )
    assert "Expanded(child: _buildContent(context))" in layout
    assert "mainAxisSize: MainAxisSize.max" in layout


def test_stack_flow_column_hoists_expanded_above_fill_width_sizedbox() -> None:
    """``flex_parent_data_direct_under_flex_host`` on phone-shell flow columns."""
    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(vertical="TOP", width=375.0, height=44.0),
        children=[],
    )
    content = CleanDesignTreeNode(
        id="content",
        name="Frame",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            width=375.0,
            height=600.0,
            height_mode=SizingMode.FIXED,
        ),
        stack_placement=StackPlacement(top=44.0, width=375.0, height=600.0),
        children=[
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Feedback",
            ),
            CleanDesignTreeNode(
                id="body",
                name="Body",
                type=NodeType.COLUMN,
                children=[],
            ),
        ],
    )
    action = CleanDesignTreeNode(
        id="action",
        name="Action",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=96.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=96.0),
        children=[],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[status, content, action, home],
    )
    layout = render_layout_file(
        screen,
        skip_layout_reconcile=True,
        feature_name="flex_parent_data_hoist",
        uses_svg=False,
    )["lib/generated/flex_parent_data_hoist_layout.dart"]
    compact = layout.replace("\n", "")
    assert "SizedBox(width: double.infinity, child: Expanded(" not in compact
    assert "Expanded(child: SingleChildScrollView" in compact


def test_pin_bottom_chrome_scroll_host_only_for_growable_panel() -> None:
    """Pin-bottom flow wraps only growable body panels in scroll hosts."""
    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(vertical="TOP", width=375.0, height=44.0),
        children=[],
    )
    nav = CleanDesignTreeNode(
        id="nav",
        name="Nav Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=56.0, height_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(top=44.0, width=375.0, height=56.0),
        children=[
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Feedback",
                stack_placement=StackPlacement(
                    left=0.0,
                    right=0.0,
                    top=19.5,
                    height=17.0,
                ),
            ),
        ],
    )
    body = CleanDesignTreeNode(
        id="body",
        name="Frame",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=600.0, height_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(top=100.0, width=375.0, height=600.0),
        children=[
            CleanDesignTreeNode(
                id="chip",
                name="Chip",
                type=NodeType.TEXT,
                text="Chip",
            ),
            CleanDesignTreeNode(
                id="form",
                name="Form",
                type=NodeType.COLUMN,
                children=[],
            ),
        ],
    )
    action = CleanDesignTreeNode(
        id="action",
        name="Action",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=96.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=96.0),
        children=[],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[status, nav, body, action, home],
    )
    body_expr = render_node_body(
        screen,
        is_layout_root=False,
        uses_svg=False,
        responsive_enabled=True,
    )
    assert body_expr.count("SingleChildScrollView") == 1
    assert "SizedBox(height: 56.0" in body_expr
    assert "SingleChildScrollView(child: Stack(" not in body_expr
    static_expr = render_node_body(screen, is_layout_root=False, uses_svg=False, responsive_enabled=False)
    assert "Expanded(child: SingleChildScrollView" not in static_expr.replace("\n", "")


def test_pin_bottom_chrome_fixed_stack_not_bare_under_scroll() -> None:
    """Fixed-height positioned stacks must not sit bare inside scroll hosts."""
    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(vertical="TOP", width=375.0, height=44.0),
        children=[],
    )
    nav = CleanDesignTreeNode(
        id="nav",
        name="Nav Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=56.0),
        stack_placement=StackPlacement(top=44.0, width=375.0, height=56.0),
        children=[
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Title",
                stack_placement=StackPlacement(left=0.0, top=19.5, height=17.0),
            ),
        ],
    )
    body = CleanDesignTreeNode(
        id="body",
        name="Body",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=500.0),
        stack_placement=StackPlacement(top=100.0, width=375.0, height=500.0),
        children=[
            CleanDesignTreeNode(id="a", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(
                id="b",
                name="B",
                type=NodeType.COLUMN,
                children=[],
            ),
        ],
    )
    action = CleanDesignTreeNode(
        id="action",
        name="Action",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=80.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=80.0),
        children=[],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[status, nav, body, action, home],
    )
    body_expr = render_node_body(screen, is_layout_root=False, uses_svg=False)
    assert "SizedBox(height: 56.0" in body_expr
    assert "SingleChildScrollView(child: Stack(" not in body_expr.replace("\n", "")


def test_flow_column_viewport_chrome_method_not_root_positioned() -> None:
    """Viewport chrome decomposed methods must not return root Positioned under flow Column."""
    from figma_flutter_agent.parser.boundaries.assets import render_boundary_asset_path

    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        stack_placement=StackPlacement(
            vertical="TOP",
            left=0.0,
            top=0.0,
            width=375.0,
            height=44.0,
        ),
        render_boundary=True,
        vector_asset_key=render_boundary_asset_path("status"),
        children=[],
    )
    body = CleanDesignTreeNode(
        id="body",
        name="Frame",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=600.0, height_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(top=44.0, width=375.0, height=600.0),
        children=[
            CleanDesignTreeNode(id="a", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(
                id="b",
                name="B",
                type=NodeType.COLUMN,
                children=[],
            ),
        ],
    )
    action = CleanDesignTreeNode(
        id="action",
        name="Action",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=96.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=96.0),
        children=[],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[status, body, action, home],
    )
    status_body = render_node_body(
        status,
        uses_svg=True,
        parent_type=NodeType.STACK,
        parent_node=screen,
    )
    assert not status_body.lstrip().startswith("Positioned(")
    assert "SvgPicture" in status_body or "SizedBox" in status_body

    screen_body = render_node_body(screen, is_layout_root=False, uses_svg=True, responsive_enabled=True)
    compact = screen_body.replace("\n", "")
    assert compact.count("SingleChildScrollView") == 1
    assert "SingleChildScrollView(child: Positioned(" not in compact


def test_sequential_raster_hero_does_not_block_column_flow() -> None:
    hero = CleanDesignTreeNode(
        id="hero",
        name="Hero",
        type=NodeType.IMAGE,
        image_asset_key="assets/images/hero.png",
        sizing=Sizing(width=327.0, height=180.0),
        stack_placement=StackPlacement(left=24.0, top=100.0, width=327.0, height=180.0),
    )
    title = CleanDesignTreeNode(
        id="title",
        name="Title",
        type=NodeType.TEXT,
        text="Food",
        sizing=Sizing(width=200.0, height=32.0),
        stack_placement=StackPlacement(left=24.0, top=300.0, width=200.0, height=32.0),
    )
    footer = CleanDesignTreeNode(
        id="footer",
        name="Footer",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=120.0),
        stack_placement=StackPlacement(
            left=0.0,
            bottom=0.0,
            width=375.0,
            height=120.0,
            vertical="BOTTOM",
        ),
        children=[],
    )
    stack = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0),
        children=[hero, title, footer],
    )
    assert stack_has_non_sequential_raster_overlay(stack) is False


def test_pin_bottom_scroll_host_uses_bounded_position_for_growable_text() -> None:
    """Growable multiline text slots must not emit ``Positioned.fill`` scroll hosts."""
    description = CleanDesignTreeNode(
        id="desc",
        name="Description",
        type=NodeType.TEXT,
        text="Line one\nLine two\nLine three",
        sizing=Sizing(width=300.0, height=80.0),
        stack_placement=StackPlacement(
            top=120.0,
            bottom=400.0,
            left=24.0,
            right=24.0,
            width=300.0,
            height=292.0,
        ),
    )
    chips = CleanDesignTreeNode(
        id="chips",
        name="Chips",
        type=NodeType.ROW,
        sizing=Sizing(width=300.0, height=48.0),
        stack_placement=StackPlacement(top=430.0, left=24.0, width=300.0, height=48.0),
        children=[],
    )
    action = CleanDesignTreeNode(
        id="action",
        name="Action",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=96.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=96.0),
        children=[],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[description, chips, action, home],
    )
    body = render_node_body(screen, is_layout_root=False, uses_svg=False, responsive_enabled=True)
    compact = body.replace("\n", "")
    assert "Positioned.fill(child: SingleChildScrollView" not in compact
    assert "SingleChildScrollView" in compact
    assert "Positioned(left: 24.0" in compact
    assert "SingleChildScrollView(child: Positioned" not in compact


def test_decomposed_absolute_stack_methods_are_not_scroll_wrapped() -> None:
    """Decomposed positioned layers must stay direct Stack children, not scroll hosts."""
    from figma_flutter_agent.generator.layout.file_methods import (
        LayoutMethod,
        compose_decomposed_root_widget,
    )

    hero = CleanDesignTreeNode(
        id="hero",
        name="Hero",
        type=NodeType.IMAGE,
        sizing=Sizing(width=177.0, height=123.0),
        stack_placement=StackPlacement(left=20.0, top=100.0, width=177.0, height=123.0),
    )
    footer = CleanDesignTreeNode(
        id="footer",
        name="Footer",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=112.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=112.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0, height_mode=SizingMode.FIXED),
        children=[hero, footer],
    )
    methods = [
        LayoutMethod(name="_buildHero", node=hero),
        LayoutMethod(name="_buildFooter", node=footer),
    ]
    layout = compose_decomposed_root_widget(
        screen,
        methods,
        responsive_enabled=False,
    )
    compact = layout.replace("\n", "")
    assert "Positioned.fill(child: SingleChildScrollView(child: _buildHero" not in compact
    assert "_buildHero(context), _buildFooter(context)" in compact


def test_wide_cta_centered_label_without_nested_positioned() -> None:
    """Wide CTAs must center labels without invalid ``Center(Positioned(...))`` trees."""
    button = CleanDesignTreeNode(
        id="cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=327.0, height=62.0),
        style=NodeStyle(background_color="0xFFFF7622", border_radius=12.0),
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Label",
                type=NodeType.TEXT,
                text="ADD TO CART",
                sizing=Sizing(width=108.0, height=20.0),
                style=NodeStyle(text_align="CENTER", text_color="0xFFFFFFFF"),
                stack_placement=StackPlacement(left=109.0, top=21.0, width=108.0, height=20.0),
            ),
        ],
    )
    body = render_node_body(button, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Center(child: Positioned(" not in compact
    assert "ADD TO CART" in compact


def test_pill_cta_centered_label_without_nested_positioned() -> None:
    """Pill CTAs must center labels without invalid ``Center(Positioned(...))`` trees."""
    button = CleanDesignTreeNode(
        id="cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=327.0, height=56.0),
        style=NodeStyle(background_color="0xFFFF7622", border_radius=28.0),
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Label",
                type=NodeType.TEXT,
                text="ADD TO CART",
                sizing=Sizing(width=327.0, height=20.0),
                stack_placement=StackPlacement(left=0.0, top=18.0, width=327.0, height=20.0),
            ),
        ],
    )
    body = render_node_body(button, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Center(child: Positioned(" not in compact
    assert "ADD TO CART" in compact
