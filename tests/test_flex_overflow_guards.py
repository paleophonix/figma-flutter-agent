"""Flex height/cross-axis guards against RenderFlex overflow."""

from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
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
                sizing=Sizing(width_mode=SizingMode.FILL),
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
    assert "height: 48.0" in body
    assert "Expanded(child: Align(alignment: Alignment.centerLeft" in body.replace(
        "\n", ""
    )


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
    from figma_flutter_agent.generator.layout_renderer import (
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
