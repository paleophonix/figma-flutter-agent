"""Flex height/cross-axis guards against RenderFlex overflow."""

from figma_flutter_agent.generator.layout.widgets.render import render_node_body
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_header_title_row_omits_fixed_height_and_column_wrapper() -> None:
    row = CleanDesignTreeNode(
        id="1:row",
        name="HeaderRow",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:btn",
                name="Back",
                type=NodeType.BUTTON,
                sizing=Sizing(width=48.0, height=48.0),
            ),
                CleanDesignTreeNode(
                    id="1:title",
                    name="TitleCol",
                    type=NodeType.COLUMN,
                    sizing=Sizing(width_mode=SizingMode.FILL, height=26.0),
                    children=[
                    CleanDesignTreeNode(
                        id="1:text",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Личные данные",
                        style=NodeStyle(font_size=17.0),
                    )
                ],
            ),
        ],
    )
    body = render_node_body(
        row,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
    )
    compact = body.replace("\n", "")
    assert "height: 48.0" in compact
    assert "Expanded(child:" in compact
    assert "Alignment.centerLeft" in compact
    assert "Личные данные" in body
    assert "SizedBox(height: 26.0, child: Align" not in compact
    assert "ConstrainedBox(constraints: BoxConstraints(minHeight: 26.0)" in compact


def test_form_field_group_allows_intrinsic_height() -> None:
    group = CleanDesignTreeNode(
        id="1:field",
        name="Field",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, height=84.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="E-mail",
                style=NodeStyle(font_size=13.0),
            ),
            CleanDesignTreeNode(
                id="1:input",
                name="Input",
                type=NodeType.INPUT,
                sizing=Sizing(width=317.0, height=52.0),
            ),
        ],
    )
    body = render_node_body(
        group,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
    )
    assert "height: 84.0" not in body
    assert "TextField" in body


def test_avatar_peer_row_uses_expanded() -> None:
    row = CleanDesignTreeNode(
        id="1:row",
        name="AvatarRow",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, height=112.0),
        children=[
            CleanDesignTreeNode(
                id="1:avatar",
                name="Avatar",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=80.0, height=80.0),
            ),
            CleanDesignTreeNode(
                id="1:side",
                name="Side",
                type=NodeType.COLUMN,
                sizing=Sizing(width_mode=SizingMode.FILL),
                children=[
                    CleanDesignTreeNode(
                        id="1:hint",
                        name="Hint",
                        type=NodeType.TEXT,
                        text="Аватар, ФИО, e-mail и дата\nрождения",
                        style=NodeStyle(font_size=14.0),
                    ),
                    CleanDesignTreeNode(
                        id="1:btn",
                        name="Update",
                        type=NodeType.BUTTON,
                        sizing=Sizing(width_mode=SizingMode.FILL, height=52.0),
                    ),
                ],
            ),
        ],
    )
    body = render_node_body(
        row,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
    )
    assert "height: 112.0" not in body
    assert "Expanded(child: Column(mainAxisSize: MainAxisSize.min" in (
        body.replace("\n", "")
    )
    from figma_flutter_agent.generator.layout.renderer import (
        _LayoutMethod,
        _stack_method_call_expr,
    )

    main = CleanDesignTreeNode(id="1:1", name="Main", type=NodeType.COLUMN)
    bottom = CleanDesignTreeNode(
        id="1:1330",
        name="BottomNavBar",
        type=NodeType.COLUMN,
        stack_placement=StackPlacement(vertical="BOTTOM", top=738.0, height=106.0),
    )
    main_call = _stack_method_call_expr(
        _LayoutMethod(name="_buildMain", node=main),
        pin_bottom_chrome=True,
    )
    bottom_call = _stack_method_call_expr(
        _LayoutMethod(name="_buildBottomnavbar", node=bottom),
        pin_bottom_chrome=True,
    )
    assert "Positioned.fill(child: SingleChildScrollView(child: _buildMain(context))" in (
        main_call
    )
    assert bottom_call == "_buildBottomnavbar(context)"


def test_space_between_row_omits_flutter_spacing_gap() -> None:
    row = CleanDesignTreeNode(
        id="1:row",
        name="Header",
        type=NodeType.ROW,
        spacing=200.9,
        alignment=Alignment(main="spaceBetween"),
        sizing=Sizing(width_mode=SizingMode.FILL, width=350.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:left",
                name="Left",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=103.0, height=48.0),
            ),
            CleanDesignTreeNode(
                id="1:right",
                name="Right",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=48.0, height=48.0),
            ),
        ],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "MainAxisAlignment.spaceBetween" in compact
    assert "spacing: 200.9" not in compact


def test_space_between_header_omits_flexible_on_fixed_chrome() -> None:
    row = CleanDesignTreeNode(
        id="1:row",
        name="Header",
        type=NodeType.ROW,
        alignment=Alignment(main="spaceBetween"),
        sizing=Sizing(width_mode=SizingMode.FILL, width=350.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:left",
                name="Left",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=103.0, height=48.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:back",
                        name="Back",
                        type=NodeType.BUTTON,
                        sizing=Sizing(width=48.0, height=48.0),
                    ),
                    CleanDesignTreeNode(
                        id="1:title",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Чаты",
                        style=NodeStyle(font_size=17.0),
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="1:right",
                name="Right",
                type=NodeType.BUTTON,
                sizing=Sizing(width=48.0, height=48.0),
            ),
        ],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", " ")
    assert "MainAxisAlignment.spaceBetween" in compact
    assert "Flexible(fit: FlexFit.loose" not in compact


def test_tight_stack_timestamp_column_uses_align_not_column() -> None:
    timestamp = CleanDesignTreeNode(
        id="1:stamp-col",
        name="Timestamp",
        type=NodeType.COLUMN,
        padding=Padding(bottom=1.0),
        sizing=Sizing(height_mode=SizingMode.FIXED, width=86.0, height=19.0),
        alignment=Alignment(cross="end"),
        stack_placement=StackPlacement(
            left=0.0,
            top=0.0,
            width=85.2,
            height=19.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Today, 11:42",
                sizing=Sizing(width=86.0, height=18.0),
                style=NodeStyle(
                    font_size=12.0,
                    text_align="RIGHT",
                    line_height=1.5,
                    glyph_top_offset=5.5,
                ),
            )
        ],
    )
    body = render_node_body(timestamp, uses_svg=False, parent_type=NodeType.STACK)
    compact = body.replace("\n", " ")
    assert "Align(alignment: Alignment.centerRight" in compact
    assert "Column(mainAxisAlignment" not in compact
    assert "EdgeInsets.fromLTRB(0.0, 0.0, 0.0, 1.0)" not in compact
    assert "EdgeInsets.only(top:" not in compact


def test_tight_chip_row_text_clips_with_expanded() -> None:
    chip_row = CleanDesignTreeNode(
        id="1:chip-row",
        name="ChipRow",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=64.0, height=17.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Поддержка",
                style=NodeStyle(font_size=12.0),
            )
        ],
    )
    body = render_node_body(chip_row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "Expanded(child:" in compact
    assert "overflow: TextOverflow.ellipsis" in compact
    assert "Flexible(fit: FlexFit.loose" not in compact


def test_scroll_content_root_column_uses_start_main_axis() -> None:
    node = CleanDesignTreeNode(
        id="362:320",
        name="Background",
        type=NodeType.COLUMN,
        sizing=Sizing(width=391.0, height=626.8),
        alignment=Alignment(main="center", cross="stretch"),
        children=[
            CleanDesignTreeNode(
                id="362:321",
                name="Container",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=357.0, height=100.0),
            )
        ],
    )
    body = render_node_body(node, uses_svg=False, scroll_content_root=True)
    assert "MainAxisAlignment.start" in body
    assert "MainAxisAlignment.center" not in body
    assert "mainAxisSize: MainAxisSize.min" in body


def test_scroll_content_root_skips_outer_positioned_for_decomposed_stack_layer() -> None:
    column = CleanDesignTreeNode(
        id="281:13256",
        name="Container",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=1358.0),
        stack_placement=StackPlacement(left=0.0, top=0.5, width=390.0, height=1358.0),
        children=[
            CleanDesignTreeNode(
                id="281:13257",
                name="Card",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=350.0, height=100.0),
            )
        ],
    )
    scroll_body = render_node_body(
        column,
        uses_svg=False,
        parent_type=NodeType.STACK,
        scroll_content_root=True,
    )
    positioned_body = render_node_body(
        column,
        uses_svg=False,
        parent_type=NodeType.STACK,
        scroll_content_root=False,
    )
    assert scroll_body.startswith("ClipRect(") or scroll_body.startswith("Column(")
    assert not scroll_body.startswith("Positioned(")
    assert positioned_body.startswith("Positioned(")


def test_bounded_positioned_column_uses_min_size_and_clip() -> None:
    column = CleanDesignTreeNode(
        id="1:card",
        name="Card",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, height=337.7),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=350.0, height=377.7),
        padding=Padding(top=20.0, right=20.0, bottom=20.0, left=20.0),
        children=[
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Support",
            )
        ],
    )
    body = render_node_body(
        column,
        uses_svg=False,
        parent_type=NodeType.STACK,
        parent_node=CleanDesignTreeNode(
            id="1:stack",
            name="Stack",
            type=NodeType.STACK,
            sizing=Sizing(width=350.0, height=400.0),
        ),
    )
    assert "mainAxisSize: MainAxisSize.min" in body
    compact = body.replace("\n", "")
    assert "Positioned(" in compact
    assert "OverflowBox(" in compact
    assert "maxHeight: double.infinity" in compact
    assert "child: ClipRect(child:" in compact
    assert "ClipRect(child: Positioned(" not in compact


def test_multiline_caption_omits_fixed_height() -> None:
    caption = CleanDesignTreeNode(
        id="1:cap",
        name="Caption",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:text",
                name="Hint",
                type=NodeType.TEXT,
                text="Аватар, ФИО, e-mail и дата\nрождения",
                style=NodeStyle(font_size=14.0),
            )
        ],
    )
    body = render_node_body(
        caption,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
    )
    assert "height: 48.0" not in body
