"""Codegen guards for profile-style chrome (back nav, avatar badge, date suffix)."""

from figma_flutter_agent.generator.layout.widgets.render import render_node_body
from figma_flutter_agent.parser.interaction import looks_like_compact_icon_action_button
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
)


def test_list_tile_button_renders_row_with_expanded_text_block() -> None:
    button = CleanDesignTreeNode(
        id="1:btn",
        name="Button",
        type=NodeType.BUTTON,
        spacing=12.0,
        sizing=Sizing(width_mode=SizingMode.FILL, width=357.0, height=80.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:icon",
                name="Background",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=48.0, height=48.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:glyph",
                        name="Vector",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=10.0, height=12.0),
                    )
                ],
            ),
            CleanDesignTreeNode(
                id="1:text",
                name="Container",
                type=NodeType.STACK,
                sizing=Sizing(width_mode=SizingMode.FILL, width=233.0, height=45.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:title-col",
                        name="Container",
                        type=NodeType.COLUMN,
                        children=[
                            CleanDesignTreeNode(
                                id="1:title",
                                name="Title",
                                type=NodeType.TEXT,
                                text="Адреса доставки",
                            )
                        ],
                    ),
                    CleanDesignTreeNode(
                        id="1:sub-col",
                        name="Container",
                        type=NodeType.COLUMN,
                        children=[
                            CleanDesignTreeNode(
                                id="1:sub",
                                name="Subtitle",
                                type=NodeType.TEXT,
                                text="2 сохраненных адреса",
                            )
                        ],
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id="1:chev",
                name="SVG",
                type=NodeType.STACK,
                sizing=Sizing(width_mode=SizingMode.FIXED, width=20.0, height=20.0),
                children=[],
            ),
        ],
    )
    body = render_node_body(button, uses_svg=False, parent_type=NodeType.COLUMN)
    assert "Row(" in body
    assert "Expanded(child:" in body
    assert "fit: StackFit.expand" not in body


def test_compact_icon_button_emits_bounded_sized_box() -> None:
    button = CleanDesignTreeNode(
        id="1:back",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=48.0, height=48.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:icon",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=5.0, height=10.0),
                style=NodeStyle(has_stroke=True, border_color="0xFF52525C"),
            )
        ],
    )
    assert looks_like_compact_icon_action_button(button)
    body = render_node_body(button, uses_svg=False, parent_type=NodeType.ROW)
    assert "SizedBox(width: 48.0, height: 48.0" in body
    assert "chevron_left" in body or "Icons." in body
    assert "Color(0xFFF6F6F2)" in body
    assert "back-nav" in body
    assert "shape: const CircleBorder()" not in body
    assert "Positioned(" not in body
    assert "chevron_left" in body


def test_explicit_multiline_caption_splits_figma_line_breaks() -> None:
    caption = CleanDesignTreeNode(
        id="1:cap",
        name="Caption",
        type=NodeType.TEXT,
        text="Аватар, ФИО, e-mail и дата\nрождения",
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=48.0),
        style=NodeStyle(
            text_color="0xFF71717B",
            font_size=14.0,
            line_height=1.71,
            text_align="LEFT",
        ),
    )
    body = render_node_body(caption, uses_svg=False, parent_type=NodeType.COLUMN)
    assert "Text('Аватар, ФИО, e-mail и дата\\nрождения'" in body
    assert "maxLines: 1" not in body
    assert "softWrap: false" in body
    assert "SizedBox(width: double.infinity" in body


def test_avatar_column_stretches_fill_children_under_row() -> None:
    caption = CleanDesignTreeNode(
        id="1:cap",
        name="Caption",
        type=NodeType.TEXT,
        text="Аватар, ФИО, e-mail и дата\nрождения",
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=48.0),
        style=NodeStyle(
            text_color="0xFF71717B",
            font_size=14.0,
            line_height=1.71,
            text_align="LEFT",
        ),
    )
    button = CleanDesignTreeNode(
        id="1:cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            width=221.0,
            height_mode=SizingMode.FIXED,
            height=52.0,
        ),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Обновить аватар",
                type=NodeType.TEXT,
                text="Обновить аватар",
                style=NodeStyle(text_color="0xFF27272A", font_size=14.0, font_weight="w600"),
            )
        ],
    )
    column = CleanDesignTreeNode(
        id="1:col",
        name="Container",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=112.0),
        alignment=Alignment(cross="center"),
        children=[caption, button],
    )
    avatar = CleanDesignTreeNode(
        id="1:avatar",
        name="Avatar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=80.0, height=80.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=112.0),
        children=[avatar, column],
    )
    body = render_node_body(row, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Expanded(child: SizedBox(height: 112.0, child: Column(" in compact
    assert "crossAxisAlignment: CrossAxisAlignment.stretch" in compact
    assert "SizedBox(width: double.infinity" in compact
    assert "Flexible(fit: FlexFit.loose, child: SizedBox(width: 80.0" not in compact
    assert "Align(alignment: Alignment.centerLeft, child: Column(" not in compact
    assert "дата\\nрождения" in body
    assert "StackFit.expand" in compact


def test_avatar_row_under_column_parent_keeps_expanded_column_stretch() -> None:
    """Width-fill Row under Column must not relax nested Expanded Column stretch."""
    caption = CleanDesignTreeNode(
        id="1:cap",
        name="Caption",
        type=NodeType.TEXT,
        text="Line one\nLine two",
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=48.0),
        style=NodeStyle(text_color="0xFF71717B", font_size=14.0, line_height=1.71),
    )
    button = CleanDesignTreeNode(
        id="1:cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            width=221.0,
            height_mode=SizingMode.FIXED,
            height=52.0,
        ),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Action",
                type=NodeType.TEXT,
                text="Action",
                style=NodeStyle(text_color="0xFF27272A", font_size=14.0),
            )
        ],
    )
    column = CleanDesignTreeNode(
        id="1:col",
        name="Container",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=221.0, height=112.0),
        alignment=Alignment(cross="center"),
        children=[caption, button],
    )
    avatar = CleanDesignTreeNode(
        id="1:avatar",
        name="Avatar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=80.0, height=80.0),
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=112.0),
        children=[avatar, column],
    )
    card = CleanDesignTreeNode(
        id="1:card",
        name="Card",
        type=NodeType.COLUMN,
        sizing=Sizing(width_mode=SizingMode.FILL, width=357.0, height=200.0),
        children=[row],
    )
    body = render_node_body(card, uses_svg=False, parent_type=NodeType.COLUMN)
    assert "Expanded(child: SizedBox(height: 112.0, child: Column(" in body
    assert "crossAxisAlignment: CrossAxisAlignment.stretch" in body
    assert "crossAxisAlignment: CrossAxisAlignment.start, spacing: 12.0" not in body


def test_fill_width_pill_button_expands_ink_surface() -> None:
    button = CleanDesignTreeNode(
        id="1:cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            width=221.0,
            height_mode=SizingMode.HUG,
            height=52.0,
        ),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=99.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Обновить аватар",
                type=NodeType.TEXT,
                text="Обновить аватар",
                sizing=Sizing(width=119.0, height=21.0),
                style=NodeStyle(
                    text_color="0xFF27272A",
                    font_size=14.0,
                    font_weight="w600",
                    text_align="CENTER",
                ),
            )
        ],
    )
    body = render_node_body(button, uses_svg=False, parent_type=NodeType.COLUMN)
    assert "SizedBox(width: double.infinity" in body
    assert "StackFit.expand" in body
    assert "Color(0xFFF6F6F2)" in body


def test_multi_child_button_wraps_padding_around_stack_not_siblings() -> None:
    """Figma list-card buttons pad the whole overlay stack, not each child."""
    icon_rail = CleanDesignTreeNode(
        id="1:icon",
        name="Icon",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=48.0, height=48.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:vector",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=20.0, height=20.0),
            )
        ],
    )
    text_overlay = CleanDesignTreeNode(
        id="1:copy",
        name="Copy",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Адреса доставки",
                sizing=Sizing(width=200.0, height=22.0),
                style=NodeStyle(
                    text_color="0xFF09090B",
                    font_size=14.0,
                    font_weight="w600",
                ),
            )
        ],
    )
    button = CleanDesignTreeNode(
        id="1:row",
        name="Button",
        type=NodeType.BUTTON,
        padding=Padding(left=16.0, top=16.0, right=16.0, bottom=16.0),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            width=329.0,
            height_mode=SizingMode.FIXED,
            height=80.0,
        ),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=24.0),
        children=[icon_rail, text_overlay],
    )
    body = render_node_body(button, uses_svg=False, parent_type=NodeType.COLUMN)
    assert (
        "Padding(padding: const EdgeInsets.fromLTRB(16.0, 16.0, 16.0, 16.0), child: Stack("
        in body
    )
    assert "child: Container(" not in body.split("Padding(padding:")[1].split("Stack(")[0]


def test_centered_glyph_badge_uses_center_without_padding() -> None:
    badge = CleanDesignTreeNode(
        id="1:avatar",
        name="Background",
        type=NodeType.ROW,
        padding={"top": 21.6, "bottom": 22.4},
        sizing=Sizing(width_mode=SizingMode.FIXED, width=80.0, height=80.0),
        alignment={"main": "center", "cross": "center"},
        style=NodeStyle(background_color="0xFFEEF9F0", border_radius=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:glyph",
                name="Initial",
                type=NodeType.TEXT,
                text="И",
                sizing=Sizing(width=19.0, height=36.0),
                style=NodeStyle(
                    text_color="0xFF2E7D32",
                    font_size=24.0,
                    font_weight="w700",
                    text_align="CENTER",
                    line_height=1.5,
                    glyph_top_offset=10.2,
                    glyph_height=16.8,
                ),
            )
        ],
    )
    body = render_node_body(badge, uses_svg=False)
    assert "Center(child:" in body
    assert "Flexible(" not in body
    assert "Padding(padding: const EdgeInsets.fromLTRB(0.0, 21.6" not in body
