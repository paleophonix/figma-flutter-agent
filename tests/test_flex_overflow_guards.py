"""Flex height/cross-axis guards against RenderFlex overflow."""

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets import render_node_body
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


def _address_style_stacked_text_button() -> CleanDesignTreeNode:
    """Minimal address-card button: spaced title/subtitle ``Column`` under ``BUTTON``."""
    body_col = CleanDesignTreeNode(
        id="1:body_col",
        name="Body",
        type=NodeType.COLUMN,
        spacing=4.0,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=282.9,
            height=48.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:title_col",
                name="Title",
                type=NodeType.COLUMN,
                sizing=Sizing(
                    width_mode=SizingMode.FILL,
                    height_mode=SizingMode.FIXED,
                    width=282.9,
                    height=23.0,
                ),
                children=[
                    CleanDesignTreeNode(
                        id="1:title",
                        name="Office",
                        type=NodeType.TEXT,
                        text="Office",
                        style=NodeStyle(
                            font_size=15.0,
                            font_weight="w600",
                            text_color="0xFF09090B",
                            line_height=1.5,
                        ),
                        sizing=Sizing(
                            width_mode=SizingMode.FILL,
                            width=282.9,
                            height=23.0,
                        ),
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:subtitle",
                name="Subtitle",
                type=NodeType.STACK,
                sizing=Sizing(
                    width_mode=SizingMode.FILL,
                    height_mode=SizingMode.FIXED,
                    width=282.9,
                    height=21.0,
                ),
                children=[
                    CleanDesignTreeNode(
                        id="1:subtitle_text",
                        name="Line",
                        type=NodeType.TEXT,
                        text="City, street, 54",
                        style=NodeStyle(
                            font_size=14.0,
                            text_color="0xFF71717B",
                            line_height=1.5,
                        ),
                        sizing=Sizing(width=255.0, height=21.0),
                        stack_placement=StackPlacement(
                            left=0.0,
                            bottom=0.9,
                            width=255.0,
                            height=21.0,
                        ),
                    )
                ],
            ),
        ],
    )
    return CleanDesignTreeNode(
        id="1:btn",
        name="AddressCard",
        type=NodeType.BUTTON,
        padding=Padding(top=16.1, bottom=16.1, left=16.1, right=16.1),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=317.0,
            height=82.1,
        ),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius=24.0,
            border_color="0xFFE4E4E7",
            border_width=1.0,
            has_stroke=True,
        ),
        children=[body_col],
    )


def test_stacked_text_button_skips_fixed_height_in_column_parent() -> None:
    """Address-style buttons must not be re-capped when finalized under a ``Column``."""
    button = _address_style_stacked_text_button()
    parent = CleanDesignTreeNode(
        id="1:parent",
        name="Cards",
        type=NodeType.COLUMN,
        spacing=12.0,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=317.0,
            height=176.3,
        ),
        children=[button],
    )
    body = render_node_body(
        parent,
        uses_svg=False,
        parent_type=NodeType.COLUMN,
    )
    compact = body.replace("\n", "")
    assert "StackFit.loose" in compact
    assert "Column(mainAxisSize: MainAxisSize.min" in compact
    assert "SizedBox(width: double.infinity, height: 82.1" not in compact
    assert "SizedBox(width: 317.0, height: 82.1" not in compact


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
    from figma_flutter_agent.generator.layout.file_methods import (
        LayoutMethod,
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
        LayoutMethod(name="_buildMain", node=main),
        pin_bottom_chrome=True,
    )
    bottom_call = _stack_method_call_expr(
        LayoutMethod(name="_buildBottomnavbar", node=bottom),
        pin_bottom_chrome=True,
    )
    assert "Positioned.fill(child: SingleChildScrollView(child: _buildMain(context))" in (
        main_call.replace("\n", "")
    ) or "Positioned.fill(child: SingleChildScrollView(padding:" in main_call.replace(
        "\n", ""
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


def test_space_between_row_binds_fixed_stack_width_and_height() -> None:
    """Fixed stacks in ``spaceBetween`` rows must not receive unbounded width."""
    label_stack = CleanDesignTreeNode(
        id="1:label-stack",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=50.5, height=21.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Items",
                type=NodeType.TEXT,
                text="Items",
                sizing=Sizing(width=50.8, height=21.0),
                style=NodeStyle(font_size=14.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    left=-0.1,
                    top=-1.0,
                    bottom=1.0,
                    width=50.8,
                    height=21.0,
                ),
            )
        ],
    )
    value_stack = CleanDesignTreeNode(
        id="1:value-stack",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=44.3, height=21.0),
        children=[
            CleanDesignTreeNode(
                id="1:value",
                name="Total",
                type=NodeType.TEXT,
                text="1194 ₽",
                sizing=Sizing(width=44.7, height=21.0),
                style=NodeStyle(font_size=14.0, text_align="RIGHT"),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    horizontal="LEFT_RIGHT",
                    top=-1.0,
                    bottom=1.0,
                    width=44.7,
                    height=21.0,
                ),
            )
        ],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="SummaryRow",
        type=NodeType.ROW,
        alignment=Alignment(main="spaceBetween", cross="center"),
        sizing=Sizing(width_mode=SizingMode.FILL, width=350.0, height=29.0),
        children=[label_stack, value_stack],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", " ")
    assert "MainAxisAlignment.spaceBetween" in compact
    assert "SizedBox(width: 50.5," in compact and "child: Stack(" in compact
    assert "SizedBox(width: 44.3," in compact and "child: Stack(" in compact
    assert "SizedBox(height: 21.0, child: Stack(" not in compact


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
    assert "maxHeight: 377.7" in compact
    assert "child: ClipRect(child:" in compact
    assert "ClipRect(child: Positioned(" not in compact


def test_overflow_box_max_height_includes_host_padding() -> None:
    """``OverflowBox`` wraps post-padding widget — maxHeight must be full slot, not inner span."""
    header = CleanDesignTreeNode(
        id="1:header",
        name="Header",
        type=NodeType.COLUMN,
        padding=Padding(top=20.0, right=20.0, bottom=16.0, left=20.0),
        sizing=Sizing(width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED, width=397.0, height=84.0),
        stack_placement=StackPlacement(left=-20.0, right=-20.0, bottom=20.0, width=397.0, height=84.0),
        children=[
            CleanDesignTreeNode(
                id="1:row",
                name="Toolbar",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, width=357.0, height=48.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:title",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Order history",
                    )
                ],
            )
        ],
    )
    body = render_node_body(
        header,
        uses_svg=False,
        parent_type=NodeType.STACK,
        parent_node=CleanDesignTreeNode(
            id="1:stack",
            name="Stack",
            type=NodeType.STACK,
            sizing=Sizing(width=357.0, height=104.0),
        ),
    )
    compact = body.replace("\n", "")
    assert "maxHeight: 84.0" in compact
    assert "maxHeight: 48.0" not in compact


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


def test_stat_metric_column_omits_fixed_container_height() -> None:
    """Metric pills are FILL columns with wrapped text lines — no height cap."""
    pill = CleanDesignTreeNode(
        id="1:pill",
        name="Background",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, height_mode=SizingMode.FILL, height=71.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=22.0),
        padding=Padding(top=12.0, right=16.0, bottom=12.0, left=16.0),
        children=[
            CleanDesignTreeNode(
                id="1:value-wrap",
                name="Container",
                type=NodeType.COLUMN,
                sizing=Sizing(height=23.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:value",
                        name="15%",
                        type=NodeType.TEXT,
                        text="15%",
                        style=NodeStyle(font_size=15.0),
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:label-wrap",
                name="Container",
                type=NodeType.COLUMN,
                sizing=Sizing(height=20.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:label",
                        name="Скидка",
                        type=NodeType.TEXT,
                        text="Скидка",
                        style=NodeStyle(font_size=13.0),
                    )
                ],
            ),
        ],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Stats",
        type=NodeType.ROW,
        spacing=8.0,
        sizing=Sizing(width_mode=SizingMode.FILL, height=75.0),
        children=[pill, pill, pill],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "minHeight: 71.0" in compact
    assert "Container(height: 71.0" not in compact


def test_flow_stack_row_peer_uses_min_height_not_fixed_cap() -> None:
    """Profile-style flow stacks must grow past fractional Figma bbox height."""
    from figma_flutter_agent.schemas import StackPlacement

    stack = CleanDesignTreeNode(
        id="1:stack",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FILL, height_mode=SizingMode.FILL, height=214.4),
        children=[
            CleanDesignTreeNode(
                id="1:name",
                name="Container",
                type=NodeType.COLUMN,
                sizing=Sizing(height=26.8),
                stack_placement=StackPlacement(top=0.0, height=26.8),
                children=[
                    CleanDesignTreeNode(
                        id="1:name-text",
                        name="Name",
                        type=NodeType.TEXT,
                        text="Иван Иванов",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:phone",
                name="Container",
                type=NodeType.COLUMN,
                sizing=Sizing(height=21.9),
                stack_placement=StackPlacement(top=42.8, height=21.9),
                children=[
                    CleanDesignTreeNode(
                        id="1:phone-text",
                        name="Phone",
                        type=NodeType.TEXT,
                        text="+7 988 200 16 32",
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:field",
                name="Label",
                type=NodeType.COLUMN,
                sizing=Sizing(height=84.0),
                stack_placement=StackPlacement(top=120.0, height=84.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:field-label",
                        name="Label",
                        type=NodeType.TEXT,
                        text="Дата рождения",
                    ),
                    CleanDesignTreeNode(
                        id="1:input",
                        name="Input",
                        type=NodeType.INPUT,
                        sizing=Sizing(width_mode=SizingMode.FILL, height=52.0),
                    ),
                ],
            ),
        ],
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Header",
        type=NodeType.ROW,
        spacing=16.0,
        sizing=Sizing(width_mode=SizingMode.FILL, height=214.4),
        children=[
            CleanDesignTreeNode(
                id="1:avatar",
                name="Avatar",
                type=NodeType.ROW,
                sizing=Sizing(width=64.0, height=64.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:glyph",
                        name="И",
                        type=NodeType.TEXT,
                        text="И",
                    )
                ],
            ),
            stack,
        ],
    )
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "Expanded(child:" in compact
    assert "SizedBox(height: 214.4" not in compact
    assert "minHeight: 214.4" in compact


def test_stack_with_bottom_nav_wraps_scrollable_layers() -> None:
    content = CleanDesignTreeNode(
        id="1:content",
        name="Content",
        type=NodeType.COLUMN,
        padding=Padding(top=20.0),
        sizing=Sizing(width=357.0, height=1200.0),
        children=[
            CleanDesignTreeNode(id="1:text", name="Title", type=NodeType.TEXT, text="Hello"),
        ],
    )
    bottom_nav = CleanDesignTreeNode(
        id="1:nav",
        name="BottomNavBar",
        type=NodeType.BOTTOM_NAV,
        sizing=Sizing(width=390.0, height=81.0),
        stack_placement=StackPlacement(horizontal="CENTER", vertical="BOTTOM", height=81.0),
        style=NodeStyle(background_blur=20.0, background_color="0xFFFFFFFF"),
        children=[
            CleanDesignTreeNode(
                id="1:row",
                name="Container",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=81.0),
            )
        ],
    )
    stack = CleanDesignTreeNode(
        id="1:stack",
        name="Screen",
        type=NodeType.STACK,
        padding=Padding(bottom=272.0),
        sizing=Sizing(width=390.0, height=844.0),
        children=[content, bottom_nav],
    )
    body = render_node_body(stack, uses_svg=False, is_layout_root=True)
    compact = body.replace("\n", "")
    assert "Positioned.fill(child: SingleChildScrollView(" in compact
    assert "padding: const EdgeInsets.only(bottom: 272.0)" in compact
    assert "Positioned(" in compact
    assert compact.count("SingleChildScrollView(") >= 1
    assert "height: 844.0" not in compact


def test_column_root_with_docked_stack_uses_viewport_not_outer_scroll() -> None:
    stack = CleanDesignTreeNode(
        id="1:stack",
        name="Container",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:content",
                name="Content",
                type=NodeType.COLUMN,
                children=[
                    CleanDesignTreeNode(id="1:text", name="A", type=NodeType.TEXT, text="A"),
                ],
            ),
            CleanDesignTreeNode(
                id="1:nav",
                name="BottomNavBar",
                type=NodeType.BOTTOM_NAV,
                sizing=Sizing(width=390.0, height=81.0),
                stack_placement=StackPlacement(vertical="BOTTOM", height=81.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:row",
                        name="Container",
                        type=NodeType.ROW,
                        sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=81.0),
                    )
                ],
            ),
        ],
    )
    root = CleanDesignTreeNode(
        id="1:root",
        name="Background",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=1697.0),
        children=[stack],
    )
    layout = render_layout_file(root, feature_name="docked_nav", uses_svg=False)[
        "lib/generated/docked_nav_layout.dart"
    ]
    compact = layout.replace("\n", "")
    assert "viewportHeight" in compact
    assert compact.count("SingleChildScrollView(") >= 1
    scroll_idx = compact.find("SingleChildScrollView(")
    viewport_idx = compact.find("viewportHeight")
    assert viewport_idx < scroll_idx or "Positioned.fill(child: SingleChildScrollView(" in compact
    assert "height: 1697.0, child: Stack" not in compact
    assert "height: 844.0, child: Stack" not in compact
    assert "height: double.infinity, child: Stack" not in compact
    assert "Expanded(child:" in compact
    assert "child: Stack(clipBehavior:" in compact
    assert "Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded" not in compact
