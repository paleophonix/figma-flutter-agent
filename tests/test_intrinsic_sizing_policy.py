"""Intrinsic sizing policy consistency across flex finalize passes."""

from __future__ import annotations

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.flex_policy import (
    _column_spaced_stack_sizes_intrinsically,
    _flex_child_should_bind_fixed_height,
    wrap_column_child_width_fill,
)
from figma_flutter_agent.parser.interaction import (
    button_has_composite_row_body,
    button_has_list_tile_row_body,
    button_hosts_stacked_text_column,
    host_prefers_intrinsic_extent,
)
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


def _subtitle_stack(*, width: float = 282.9) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:sub_stack",
        name="Subtitle",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=width,
            height=21.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:sub_text",
                name="Address line",
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
    )


def _title_column(*, label: str = "Office", width: float = 282.9) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:title_col",
        name="Title",
        type=NodeType.COLUMN,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=width,
            height=23.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:title_text",
                name=label,
                type=NodeType.TEXT,
                text=label,
                style=NodeStyle(
                    font_size=15.0,
                    font_weight="w600",
                    text_color="0xFF09090B",
                    line_height=1.5,
                ),
                sizing=Sizing(width_mode=SizingMode.FILL, width=width, height=23.0),
            )
        ],
    )


def _spaced_metadata_column(*, with_inner_row: bool) -> CleanDesignTreeNode:
    if with_inner_row:
        preview = CleanDesignTreeNode(
            id="1:preview",
            name="Preview",
            type=NodeType.TEXT,
            text="Last message preview",
            style=NodeStyle(font_size=14.0, text_color="0xFF71717B"),
            sizing=Sizing(width_mode=SizingMode.FILL, width=200.0, height=20.0),
        )
        title_child: CleanDesignTreeNode = CleanDesignTreeNode(
            id="1:title_row",
            name="TitleRow",
            type=NodeType.ROW,
            spacing=8.0,
            sizing=Sizing(width_mode=SizingMode.FILL, width=200.0, height=22.0),
            children=[
                CleanDesignTreeNode(
                    id="1:name",
                    name="Name",
                    type=NodeType.TEXT,
                    text="Contact",
                    style=NodeStyle(font_size=16.0, font_weight="w600"),
                    sizing=Sizing(width_mode=SizingMode.FILL, width=120.0, height=22.0),
                ),
                CleanDesignTreeNode(
                    id="1:time",
                    name="Time",
                    type=NodeType.TEXT,
                    text="12:30",
                    style=NodeStyle(font_size=12.0, text_color="0xFF71717B"),
                    sizing=Sizing(width=48.0, height=18.0),
                ),
            ],
        )
        children = [title_child, preview]
    else:
        children = [_title_column(label="Home"), _subtitle_stack()]

    return CleanDesignTreeNode(
        id="1:meta_col",
        name="Metadata",
        type=NodeType.COLUMN,
        spacing=4.0,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=282.9,
            height=48.0,
        ),
        children=children,
    )


def _stacked_text_button() -> CleanDesignTreeNode:
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
        children=[_spaced_metadata_column(with_inner_row=False)],
    )


def _composite_row_button() -> CleanDesignTreeNode:
    metadata = CleanDesignTreeNode(
        id="1:badge_col",
        name="Badge",
        type=NodeType.COLUMN,
        sizing=Sizing(width=72.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:badge",
                name="Primary",
                type=NodeType.TEXT,
                text="Primary",
                style=NodeStyle(font_size=12.0, font_weight="w600", text_color="0xFF2E7D32"),
                sizing=Sizing(width=72.0, height=20.0),
            )
        ],
    )
    body_row = CleanDesignTreeNode(
        id="1:body_row",
        name="Body",
        type=NodeType.ROW,
        spacing=12.0,
        alignment=Alignment(main="spaceBetween", cross="stretch"),
        sizing=Sizing(width_mode=SizingMode.FILL, width=282.9, height=48.0),
        children=[
            _spaced_metadata_column(with_inner_row=False),
            metadata,
        ],
    )
    return CleanDesignTreeNode(
        id="1:btn_row",
        name="AddressCardRow",
        type=NodeType.BUTTON,
        padding=Padding(top=16.1, bottom=16.1, left=16.1, right=16.1),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=317.0,
            height=82.1,
        ),
        style=NodeStyle(
            background_color="0xFFEEF9F0",
            border_radius=24.0,
            border_color="0xFFC4E9CB",
            border_width=1.0,
            has_stroke=True,
        ),
        children=[body_row],
    )


def test_intrinsic_button_predicates_skip_fixed_height_binding() -> None:
    stacked = _stacked_text_button()
    composite = _composite_row_button()
    assert button_hosts_stacked_text_column(stacked)
    assert button_has_composite_row_body(composite)
    assert not button_has_list_tile_row_body(stacked)

    for node in (stacked, composite):
        assert not _flex_child_should_bind_fixed_height(node)


def test_spaced_metadata_column_skips_fixed_height_binding() -> None:
    address_column = _spaced_metadata_column(with_inner_row=False)
    chat_column = _spaced_metadata_column(with_inner_row=True)

    assert _column_spaced_stack_sizes_intrinsically(address_column)
    assert not _column_spaced_stack_sizes_intrinsically(chat_column)
    assert not _flex_child_should_bind_fixed_height(address_column)
    assert not _flex_child_should_bind_fixed_height(chat_column)


def test_wrap_column_child_width_fill_respects_intrinsic_hosts() -> None:
    stacked = _stacked_text_button()
    inner = "Placeholder(child: Text('x'))"
    wrapped = wrap_column_child_width_fill(inner, stacked)
    compact = wrapped.replace("\n", "")
    assert "height: 82.1" not in compact
    assert "SizedBox(width:" in compact


def test_row_cross_axis_height_clamps_inflated_icon_wrapper_row() -> None:
    """Law: LAW-STATUS-CHROME-SLOT-HEIGHT-CLAMP — icon wrapper ROW uses inner intrinsic height."""
    from figma_flutter_agent.generator.layout.flex_policy.extents import bind_row_cross_axis_height

    battery_stack = CleanDesignTreeNode(
        id="266:1648",
        name="Battery",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
    )
    battery_row = CleanDesignTreeNode(
        id="266:1647",
        name="Battery",
        type=NodeType.ROW,
        sizing=Sizing(width=16.0, height=52.0),
        children=[battery_stack],
    )
    status_row = CleanDesignTreeNode(
        id="266:1499",
        name="Status",
        type=NodeType.ROW,
        sizing=Sizing(width=360.0, height=40.0),
        children=[battery_row],
    )
    pinned = bind_row_cross_axis_height(
        battery_row,
        "Stack(children: [const SizedBox.shrink()])",
        parent_row=status_row,
    )
    assert "height: 52.0" not in pinned.replace("\n", "")
    assert "height: 16.0" in pinned.replace("\n", "")


def test_row_cross_axis_height_pin_skips_address_but_keeps_chat_metadata() -> None:
    """Address columns size intrinsically; chat list cards keep bounded row rails."""
    from figma_flutter_agent.generator.layout.flex_policy import bind_row_cross_axis_height

    row = CleanDesignTreeNode(
        id="1:row",
        name="CardRow",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, height_mode=SizingMode.FILL, height=72.0),
        children=[],
    )
    widget = "Column(mainAxisSize: MainAxisSize.min, children: [Text('x')])"

    address_column = _spaced_metadata_column(with_inner_row=False)
    chat_column = _spaced_metadata_column(with_inner_row=True)

    address_pinned = bind_row_cross_axis_height(
        address_column,
        widget,
        parent_row=row,
    )
    chat_pinned = bind_row_cross_axis_height(
        chat_column,
        widget,
        parent_row=row,
    )

    assert "height: 48.0" in address_pinned.replace("\n", "")
    compact_chat = chat_pinned.replace("\n", "")
    assert "height: 48.0" in compact_chat or "minHeight: 48.0" in compact_chat


def test_row_text_cross_axis_pin_uses_line_box_when_frame_is_shorter() -> None:
    """ROW cross-axis pin must use typographic line-box, not clipped Figma glyph frame."""
    from figma_flutter_agent.generator.layout.flex_policy.extents import bind_row_cross_axis_height

    row = CleanDesignTreeNode(
        id="row",
        name="TabRow",
        type=NodeType.ROW,
        sizing=Sizing(width=160.0, height=32.0),
        children=[],
    )
    label = CleanDesignTreeNode(
        id="lbl",
        name="Log In",
        type=NodeType.TEXT,
        text="Log In",
        sizing=Sizing(width=40.0, height=10.0),
        style=NodeStyle(font_size=14.0, line_height=1.5),
    )
    pinned = bind_row_cross_axis_height(label, "Text('Log In')", parent_row=row)
    compact = pinned.replace("\n", "")
    assert "height: 21.0" in compact
    assert "height: 10.0" not in compact


def test_host_prefers_intrinsic_extent_covers_order_card_button() -> None:
    header_row = CleanDesignTreeNode(
        id="1:header",
        name="Header",
        type=NodeType.ROW,
        offset_y=0.0,
        sizing=Sizing(width=300.0, height=48.0),
        children=[],
    )
    actions_row = CleanDesignTreeNode(
        id="1:actions",
        name="Actions",
        type=NodeType.ROW,
        offset_y=60.0,
        sizing=Sizing(width=300.0, height=44.0),
        children=[],
    )
    button = CleanDesignTreeNode(
        id="1:btn",
        name="OrderCard",
        type=NodeType.BUTTON,
        spacing=12.0,
        sizing=Sizing(width=310.0, height=80.0),
        children=[header_row, actions_row],
    )
    assert host_prefers_intrinsic_extent(button)
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=844.0),
        children=[button],
    )
    layout = render_layout_file(screen, feature_name="intrinsic_btn", uses_svg=False)[
        "lib/generated/intrinsic_btn_layout.dart"
    ]
    idx = layout.find("custom-code:figma-1_btn:button-action")
    assert idx >= 0
    snippet = layout[max(0, idx - 200) : idx + 1600]
    assert "Column(mainAxisSize: MainAxisSize.min" in snippet
    assert "SizedBox(height: 48.0, child: Align" not in snippet
