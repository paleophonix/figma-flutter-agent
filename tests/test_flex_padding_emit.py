"""Codegen emits Figma auto-layout padding on flex hosts."""

from figma_flutter_agent.generator.layout.style import text_style_expr
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.theme_typography import (
    build_text_theme_size_slots,
    build_text_theme_slot_by_style_name,
)
from figma_flutter_agent.parser.interaction import looks_like_input_trailing_icon_button
from figma_flutter_agent.parser.layout import reconcile_stack_placements_in_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    LayoutSlotIr,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
    StackPlacement,
    TypographyStyle,
    WrapKind,
)


def test_column_padding_wraps_children() -> None:
    card = CleanDesignTreeNode(
        id="card",
        name="Card",
        type=NodeType.COLUMN,
        padding=Padding(top=20.0, bottom=20.0, left=20.0, right=20.0),
        sizing=Sizing(width=357.0, height=200.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=28.0),
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Label",
                type=NodeType.TEXT,
                text="Title",
                sizing=Sizing(width=100.0, height=20.0),
                style=NodeStyle(text_color="0xFF000000", font_size=14.0),
            )
        ],
    )
    body = render_node_body(card, uses_svg=False)
    assert "Padding(padding: const EdgeInsets.fromLTRB(20.0, 20.0, 20.0, 20.0)" in body
    assert "borderRadius: BorderRadius.circular(28.0)" in body


def test_trailing_input_row_does_not_pin_field_to_full_input_width() -> None:
    calendar = CleanDesignTreeNode(
        id="icon",
        name="Button menu",
        type=NodeType.BUTTON,
        sizing=Sizing(width=18.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=11.0, height=12.0),
                style=NodeStyle(background_color="0xFF000000"),
            )
        ],
    )
    field = CleanDesignTreeNode(
        id="input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=317.0, height=52.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="row",
                name="Row",
                type=NodeType.ROW,
                sizing=Sizing(width=285.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="value",
                        name="Value",
                        type=NodeType.TEXT,
                        text="14.06.1995",
                        sizing=Sizing(width=82.0, height=21.0),
                        style=NodeStyle(text_color="0xFF18181B", font_size=14.0),
                    ),
                    calendar,
                ],
            )
        ],
    )
    body = render_node_body(field, uses_svg=False)
    assert "suffixIcon:" in body
    assert "IconButton(" in body
    assert "onPressed:" in body
    assert "onTap:" not in body.split("suffixIcon:")[1].split("IconButton(")[1]
    assert "InkWell(" not in body.split("suffixIcon:")[1]
    assert "Container(width: 317.0" in body
    assert looks_like_input_trailing_icon_button(calendar)
    assert "Expanded(child:" not in body.split("suffixIcon:")[0]


def test_text_theme_prefers_font_size_over_style_name() -> None:
    tokens = DesignTokens(
        typography={
            "Heading 1": TypographyStyle(font_size=32.0, font_weight="w700"),
            "Body": TypographyStyle(font_size=14.0, font_weight="w400"),
        }
    )
    slots = build_text_theme_slot_by_style_name(tokens)
    sizes = build_text_theme_size_slots(tokens)
    node = CleanDesignTreeNode(
        id="title",
        name="Heading 1",
        type=NodeType.TEXT,
        text="Title",
        sizing=Sizing(width=120.0, height=26.0),
        style=NodeStyle(
            style_name="Heading 1",
            text_color="0xFF09090B",
            font_size=17.0,
            font_weight="w700",
        ),
    )
    expr = text_style_expr(
        node,
        text_theme_slot_by_style_name=slots,
        text_theme_size_slots=sizes,
    )
    assert "displayLarge" not in expr
    assert "fontSize: 17.0" in expr
    assert "fontWeight: FontWeight.w700" in expr


def test_fixed_width_row_child_is_not_expanded_in_avatar_row() -> None:
    avatar = CleanDesignTreeNode(
        id="avatar",
        name="Avatar",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=80.0, height=80.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="I",
                type=NodeType.TEXT,
                text="I",
                sizing=Sizing(width=19.0, height=36.0),
                style=NodeStyle(text_color="0xFF2E7D32", font_size=24.0),
            )
        ],
    )
    details = CleanDesignTreeNode(
        id="details",
        name="Details",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, height=112.0),
        spacing=12.0,
        children=[
            CleanDesignTreeNode(
                id="hint",
                name="Hint",
                type=NodeType.TEXT,
                text="Avatar, name, email",
                sizing=Sizing(width=221.0, height=48.0),
                style=NodeStyle(text_color="0xFF71717B", font_size=14.0),
            ),
            CleanDesignTreeNode(
                id="btn",
                name="Button",
                type=NodeType.BUTTON,
                sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=52.0),
                style=NodeStyle(background_color="0xFFF6F6F2", border_radius=99.0),
                children=[
                    CleanDesignTreeNode(
                        id="label",
                        name="Update",
                        type=NodeType.TEXT,
                        text="Update avatar",
                        sizing=Sizing(width=119.0, height=21.0),
                        style=NodeStyle(font_size=14.0, font_weight="w600"),
                    )
                ],
            ),
        ],
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Avatar row",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=112.0),
        children=[avatar, details],
    )
    body = render_node_body(row, uses_svg=False)
    compact = body.replace("\n", "")
    assert "spacing: 16.0" in body
    assert "Expanded(child: Container(width: 80.0" not in compact
    assert "Flexible(fit: FlexFit.loose, child: SizedBox(width: 80.0" not in compact
    assert "width: 80.0" in compact
    assert "Expanded(child:" in compact


def test_nested_form_column_does_not_reflow_to_row() -> None:
    column = CleanDesignTreeNode(
        id="form",
        name="Fields",
        type=NodeType.COLUMN,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=200.0),
        children=[
            CleanDesignTreeNode(
                id="a",
                name="A",
                type=NodeType.TEXT,
                text="Label",
                sizing=Sizing(width=100.0, height=20.0),
                style=NodeStyle(font_size=13.0),
            ),
            CleanDesignTreeNode(
                id="b",
                name="B",
                type=NodeType.INPUT,
                sizing=Sizing(width=317.0, height=52.0),
                style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
                children=[],
            ),
        ],
    )
    body = render_node_body(
        column,
        uses_svg=False,
        responsive_enabled=True,
        design_artboard_width=390.0,
        parent_type=NodeType.COLUMN,
    )
    assert "spacing: 16.0" in body
    assert "isWideLayout" not in body


def test_stack_child_placement_clamped_at_codegen() -> None:
    header_host = CleanDesignTreeNode(
        id="host",
        name="Host",
        type=NodeType.STACK,
        sizing=Sizing(width=357.0, height=104.0),
        children=[
            CleanDesignTreeNode(
                id="bar",
                name="Bar",
                type=NodeType.COLUMN,
                sizing=Sizing(width=397.0, height=84.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    left=-20.0,
                    right=-20.0,
                    bottom=20.0,
                    width=397.0,
                    height=84.0,
                ),
                children=[],
            )
        ],
    )
    body = render_node_body(
        header_host.children[0],
        uses_svg=False,
        parent_type=NodeType.STACK,
        parent_node=header_host,
    )
    assert "left: -20.0" not in body
    assert "width: 357.0" in body


def test_clamped_stack_child_syncs_sizing_width() -> None:
    parent = CleanDesignTreeNode(
        id="stack",
        name="Header host",
        type=NodeType.STACK,
        sizing=Sizing(width=357.0, height=104.0),
        children=[
            CleanDesignTreeNode(
                id="bar",
                name="Bar",
                type=NodeType.COLUMN,
                sizing=Sizing(width=397.0, height=84.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    left=-20.0,
                    right=-20.0,
                    bottom=20.0,
                    width=397.0,
                    height=84.0,
                ),
                children=[],
            )
        ],
    )
    reconciled = reconcile_stack_placements_in_tree(parent)
    bar = reconciled.children[0]
    assert bar.stack_placement is not None
    assert bar.stack_placement.width == 357.0
    assert bar.sizing.width == 357.0


def test_center_preserves_flex_parent_data_outside() -> None:
    from figma_flutter_agent.generator.layout.widgets import (
        _wrap_center_preserving_flex_parent_data,
    )

    inner = "Flexible(fit: FlexFit.loose, child: Text('Hi'))"
    wrapped = _wrap_center_preserving_flex_parent_data(inner)
    assert wrapped == "Flexible(fit: FlexFit.loose, child: Center(child: Text('Hi')))"
    assert "Center(child: Flexible(" not in wrapped


def test_sizing_constraints_keep_flexible_outside_constrained_box() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.wrap import repair_flex_parent_data_order

    misordered = (
        "ConstrainedBox(constraints: BoxConstraints(maxWidth: 160.0), "
        "child: Flexible(fit: FlexFit.loose, flex: 0, child: Text('Card')))"
    )
    repaired = repair_flex_parent_data_order(misordered)
    assert "ConstrainedBox(child: Flexible(" not in repaired
    assert repaired.startswith("Flexible(fit: FlexFit.loose")


def test_repair_flex_parent_data_order_hoists_expanded_above_fill_width_sizedbox() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.wrap import repair_flex_parent_data_order

    misordered = (
        "SizedBox(width: double.infinity, child: Expanded(child: "
        "SingleChildScrollView(child: _buildContent(context))))"
    )
    repaired = repair_flex_parent_data_order(misordered)
    assert "SizedBox(width: double.infinity, child: Expanded(" not in repaired
    assert repaired.startswith("Expanded(child: SizedBox(width: double.infinity")


def test_repair_flex_parent_data_order_hoists_expanded_above_repaint_boundary() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.wrap import repair_flex_parent_data_order

    misordered = "RepaintBoundary(child: Expanded(child: ListView.builder()))"
    repaired = repair_flex_parent_data_order(misordered)
    assert repaired == "Expanded(child: RepaintBoundary(child: ListView.builder()))"
    assert "RepaintBoundary(child: Expanded(" not in repaired


def test_repair_flex_parent_data_order_hoists_nested_misorder() -> None:
    from figma_flutter_agent.generator.layout.flex_policy.wrap import repair_flex_parent_data_order

    misordered = (
        "Expanded(child: SizedBox(child: RepaintBoundary(child: "
        "Expanded(child: SizedBox(child: Text('Hi'))))))"
    )
    repaired = repair_flex_parent_data_order(misordered)
    assert "RepaintBoundary(child: Expanded(" not in repaired
    assert repaired.startswith("Expanded(child: SizedBox(")


def test_layout_slot_repaint_boundary_keeps_expanded_outside() -> None:
    from figma_flutter_agent.generator.layout.widgets import _apply_layout_slot_wraps
    from figma_flutter_agent.schemas import LayoutSlotIr, WrapKind

    node = CleanDesignTreeNode(
        id="list",
        name="Feed",
        type=NodeType.COLUMN,
        layout_slot=LayoutSlotIr(wraps=(WrapKind.REPAINT_BOUNDARY, WrapKind.EXPANDED)),
    )
    wrapped = _apply_layout_slot_wraps(
        node,
        "ListView.builder()",
        parent_type=NodeType.COLUMN,
    )
    assert wrapped.startswith("Expanded(child: RepaintBoundary(")
    assert "RepaintBoundary(child: Expanded(" not in wrapped


def test_layout_slot_repaint_boundary_hoists_preexisting_expanded() -> None:
    from figma_flutter_agent.generator.layout.widgets import _apply_layout_slot_wraps
    from figma_flutter_agent.schemas import LayoutSlotIr, WrapKind

    node = CleanDesignTreeNode(
        id="list",
        name="Feed",
        type=NodeType.COLUMN,
        layout_slot=LayoutSlotIr(wraps=(WrapKind.REPAINT_BOUNDARY,)),
    )
    wrapped = _apply_layout_slot_wraps(
        node,
        "Expanded(child: ListView.builder())",
        parent_type=NodeType.COLUMN,
    )
    assert wrapped.startswith("Expanded(child: RepaintBoundary(")
    assert "RepaintBoundary(child: Expanded(" not in wrapped


def test_expanded_wrap_is_outside_delta_top_padding() -> None:
    from figma_flutter_agent.generator.layout.widgets import _apply_layout_slot_wraps
    from figma_flutter_agent.schemas import LayoutSlotIr, TextMetricsFrame, WrapKind

    node = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        text_metrics_frame=TextMetricsFrame(font_size=16.0, delta_top=4.0),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.EXPANDED, WrapKind.DELTA_TOP_PADDING)),
    )
    wrapped = _apply_layout_slot_wraps(
        node,
        "Text('Hi')",
        parent_type=NodeType.ROW,
    )
    assert wrapped.startswith("Expanded(child: Padding(")
    assert "Padding(child: Expanded(" not in wrapped


def test_layout_slot_skips_flex_wrap_outside_row_column() -> None:
    from figma_flutter_agent.generator.layout.widgets import _apply_layout_slot_wraps

    node = CleanDesignTreeNode(
        id="glyph",
        name="И",
        type=NodeType.TEXT,
        layout_slot=LayoutSlotIr(wraps=(WrapKind.FLEXIBLE_LOOSE,)),
    )
    wrapped = _apply_layout_slot_wraps(
        node,
        "Text('И')",
        parent_type=NodeType.STACK,
    )
    assert wrapped == "Text('И')"


def test_flex_reconcile_skips_glyph_badge_text_flex() -> None:
    from figma_flutter_agent.generator.layout import render_layout_file
    from figma_flutter_agent.generator.layout.flex_reconcile import (
        apply_flex_guards_from_tree,
    )
    from figma_flutter_agent.schemas import LayoutSlotIr

    badge = CleanDesignTreeNode(
        id="avatar",
        name="Background",
        type=NodeType.ROW,
        padding=Padding(top=20.0, bottom=20.0),
        sizing=Sizing(width=80.0, height=80.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="И",
                type=NodeType.TEXT,
                text="И",
                layout_slot=LayoutSlotIr(wraps=(WrapKind.FLEXIBLE_LOOSE,)),
                style=NodeStyle(
                    text_align="CENTER",
                    font_size=24.0,
                    text_color="0xFF2E7D32",
                ),
            )
        ],
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Avatar row",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=112.0),
        children=[badge],
    )
    source = render_layout_file(
        row,
        feature_name="avatar_row",
        uses_svg=False,
        use_geometry_planner=True,
    )["lib/generated/avatar_row_layout.dart"]
    guarded = apply_flex_guards_from_tree(source, row)
    assert "child: Flexible(" not in guarded.split("Container(width: 80.0")[1].split("Center")[0]


def test_column_stack_with_planner_wraps_gets_bounded_height() -> None:
    header_stack = CleanDesignTreeNode(
        id="margin",
        name="Margin",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=357.0,
            height=104.0,
        ),
        layout_slot=LayoutSlotIr(
            wraps=(WrapKind.CROSS_STRETCH_WIDTH, WrapKind.CONSTRAINED_BOX),
        ),
        children=[
            CleanDesignTreeNode(
                id="blur",
                name="Blur",
                type=NodeType.COLUMN,
                sizing=Sizing(width=357.0, height=84.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    horizontal="LEFT",
                    vertical="TOP",
                    left=0.0,
                    top=0.0,
                    width=357.0,
                    height=84.0,
                ),
                children=[],
            )
        ],
    )
    column = CleanDesignTreeNode(
        id="content",
        name="Content",
        type=NodeType.COLUMN,
        sizing=Sizing(width=357.0, height=200.0),
        children=[header_stack],
    )
    body = render_node_body(column, uses_svg=False)
    assert (
        "SizedBox(width: double.infinity, height: 104.0, child: SizedBox(width: 357.0, child: Stack("
        in body
    )


def test_centered_glyph_badge_avoids_nested_flex() -> None:
    badge = CleanDesignTreeNode(
        id="avatar",
        name="Background",
        type=NodeType.ROW,
        padding=Padding(top=20.0, bottom=20.0),
        sizing=Sizing(width=80.0, height=80.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            CleanDesignTreeNode(
                id="glyph",
                name="И",
                type=NodeType.TEXT,
                text="И",
                style=NodeStyle(
                    text_align="CENTER",
                    font_size=24.0,
                    text_color="0xFF2E7D32",
                ),
            )
        ],
    )
    body = render_node_body(badge, uses_svg=False, parent_type=NodeType.ROW)
    assert "Container(" in body
    assert "child: Flexible(" not in body.split("Container(", 1)[1]
