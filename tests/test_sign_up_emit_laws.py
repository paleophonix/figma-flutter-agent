"""Regression laws for auth-form emit: heading tap, back icon, calendar, prefix, preview."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import (
    artboard_static_wizard_preview,
    wrap_artboard_preview_layout_builder,
)
from figma_flutter_agent.generator.layout.scroll import padding_edge_insets_fitted_to_host
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.layout.widgets.svg import (
    stack_should_emit_flattened_vector_group,
)
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
)


def _sign_up_heading_column() -> CleanDesignTreeNode:
    heading = CleanDesignTreeNode(
        id="49:1668",
        name="Sign Up",
        type=NodeType.TEXT,
        text="Sign Up",
        sizing=Sizing(width=263.0, height=34.0),
        style=NodeStyle(
            font_size=26.0,
            font_weight="w700",
            text_align="CENTER",
        ),
    )
    return CleanDesignTreeNode(
        id="49:1667",
        name="Headline",
        type=NodeType.COLUMN,
        sizing=Sizing(width=279.0, height=63.0),
        alignment=Alignment(main="center", cross="center"),
        children=[heading],
    )


def _stroke_calendar_trailing() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="I49:1747;3:6015",
        name="calendar-due",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
        variant=ComponentVariant(
            component_id="3:14913",
            component_name="calendar-due",
        ),
        children=[
            CleanDesignTreeNode(
                id="I49:1747;3:6015;3:14914",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=10.7, height=12.0),
                style=NodeStyle(has_stroke=True, border_width=1.3, border_color="0xFFACB5BB"),
            )
        ],
    )


def _date_field_with_calendar_suffix() -> CleanDesignTreeNode:
    calendar = _stroke_calendar_trailing()
    return CleanDesignTreeNode(
        id="49:1747",
        name="Birth of date",
        type=NodeType.INPUT,
        sizing=Sizing(width=279.0, height=46.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=10.0),
        children=[
            CleanDesignTreeNode(
                id="row",
                name="Row",
                type=NodeType.ROW,
                sizing=Sizing(width=247.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="value",
                        name="Value",
                        type=NodeType.TEXT,
                        text="18/03/2024",
                        sizing=Sizing(width=225.0, height=21.0),
                        style=NodeStyle(font_size=14.0),
                    ),
                    calendar,
                ],
            )
        ],
    )


def _phone_country_prefix_row() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="I49:1748;3:6099",
        name="Country",
        type=NodeType.ROW,
        padding=Padding(top=27.0, bottom=27.0, left=14.0, right=14.0),
        sizing=Sizing(width=62.0, height=48.0),
        alignment=Alignment(cross="center"),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_width=1.0,
            border_color="0xFFEDF1F3",
            has_stroke=True,
        ),
        children=[
            CleanDesignTreeNode(
                id="flag",
                name="Countries/United Kingdom",
                type=NodeType.STACK,
                sizing=Sizing(width=18.0, height=18.0),
                children=[
                    CleanDesignTreeNode(
                        id="vec",
                        name="Vector",
                        type=NodeType.VECTOR,
                        vector_asset_key="assets/icons/flag.svg",
                        sizing=Sizing(width=18.0, height=18.0),
                    )
                ],
            )
        ],
    )


def _flattened_back_arrow_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="49:1740",
        name="arrow-narrow-left",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        component_ref="3:4467",
        variant=ComponentVariant(
            component_id="3:4467",
            component_name="arrow-narrow-left",
        ),
        vector_asset_key="assets/icons/arrow_group.svg",
        vector_svg_path_count=2,
        children=[
            CleanDesignTreeNode(
                id="vec",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=14.0, height=8.0),
                style=NodeStyle(background_color="0xFF1A1C1E"),
            )
        ],
    )


def test_static_heading_text_not_wrapped_in_gesture_detector() -> None:
    body = render_node_body(_sign_up_heading_column(), uses_svg=False)
    assert "Text('Sign Up'" in body
    assert "GestureDetector(" not in body
    assert "MouseRegion(" not in body


def test_date_field_with_calendar_due_suffix_uses_calendar_icon() -> None:
    body = render_node_body(_date_field_with_calendar_suffix(), uses_svg=False)
    assert "calendar_today_outlined" in body
    assert "keyboard_arrow_down_outlined" not in body


def test_phone_country_prefix_padding_fits_host_height() -> None:
    insets = padding_edge_insets_fitted_to_host(_phone_country_prefix_row())
    assert insets is not None
    assert "27.0" not in insets
    body = render_node_body(_phone_country_prefix_row(), uses_svg=True)
    assert "27.0" not in body


def test_flattened_back_arrow_export_emits_tap_target() -> None:
    node = _flattened_back_arrow_stack()
    assert stack_should_emit_flattened_vector_group(node)
    body = render_node_body(node, uses_svg=True)
    assert "InkWell(" in body or "GestureDetector(" in body
    assert "back-nav" in body or "button-action" in body


def test_wizard_preview_does_not_paint_opaque_artboard_overlay() -> None:
    preview = artboard_static_wizard_preview(scroll_child="child")
    assert "ColoredBox(color: Color(0xFF1E1E1E)" not in preview
    wrapped = wrap_artboard_preview_layout_builder(
        preview_child="SizedBox(width: previewW, height: previewH, child: child)",
        fallback="child",
        scroll_child="SizedBox(width: previewW, height: previewH, child: child)",
    )
    assert "ColoredBox(color: Color(0xFF1E1E1E)" not in wrapped
