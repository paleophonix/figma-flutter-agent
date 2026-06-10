"""Button bodies with vertically stacked rows must emit Column, not Stack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.interaction import button_should_flow_as_column
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


def _text_node(
    node_id: str,
    *,
    text: str,
    width: float,
    height: float,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=text,
        type=NodeType.TEXT,
        text=text,
        style=NodeStyle(font_size=13.0, font_weight="w600"),
        sizing=Sizing(width=width, height=height),
    )


def _order_card_button() -> CleanDesignTreeNode:
    header_row = CleanDesignTreeNode(
        id="1:header_row",
        name="Header",
        type=NodeType.ROW,
        offset_y=0.0,
        alignment=Alignment(main="spaceBetween", cross="start"),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=282.0,
            height=48.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:meta_col",
                name="Meta",
                type=NodeType.COLUMN,
                spacing=7.0,
                sizing=Sizing(width_mode=SizingMode.FILL, width=180.0, height=48.0),
                children=[
                    _text_node("1:title", text="Order title", width=180.0, height=20.0),
                    _text_node("1:subtitle", text="Today, 13:00", width=180.0, height=18.0),
                ],
            ),
            CleanDesignTreeNode(
                id="1:badge",
                name="Badge",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=81.0, height=25.0),
                style=NodeStyle(background_color="0xFFEEF9F0", border_radius=12.5),
                children=[
                    _text_node("1:badge_text", text="Status", width=57.0, height=16.0),
                ],
            ),
        ],
    )
    actions_row = CleanDesignTreeNode(
        id="1:actions_row",
        name="Actions",
        type=NodeType.ROW,
        offset_y=56.0,
        spacing=8.0,
        alignment=Alignment(main="start", cross="start"),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=282.0,
            height=44.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:action_a",
                name="ActionA",
                type=NodeType.BUTTON,
                sizing=Sizing(width=150.0, height=44.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_radius=99.0,
                    border_color="0xFFE4E4E7",
                    border_width=1.0,
                    has_stroke=True,
                ),
                children=[_text_node("1:action_a_label", text="Card", width=80.0, height=18.0)],
            ),
            CleanDesignTreeNode(
                id="1:action_b",
                name="ActionB",
                type=NodeType.BUTTON,
                sizing=Sizing(width=150.0, height=44.0),
                style=NodeStyle(background_color="0xFF28A745", border_radius=99.0),
                children=[_text_node("1:action_b_label", text="Track", width=80.0, height=18.0)],
            ),
        ],
    )
    return CleanDesignTreeNode(
        id="1:card_button",
        name="OrderCard",
        type=NodeType.BUTTON,
        padding=Padding(top=20.0, bottom=20.0, left=20.0, right=20.0),
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            height_mode=SizingMode.FIXED,
            width=322.0,
            height=120.0,
        ),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius=28.0,
            border_color="0xFFE4E4E7",
            border_width=1.0,
            has_stroke=True,
        ),
        children=[header_row, actions_row],
    )


def _overlay_icon_button() -> CleanDesignTreeNode:
    surface = CleanDesignTreeNode(
        id="1:surface",
        name="Bg",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=200.0, height=44.0),
        style=NodeStyle(background_color="0xFF28A745", border_radius=22.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=200.0, height=44.0),
    )
    label = CleanDesignTreeNode(
        id="1:label",
        name="Label",
        type=NodeType.TEXT,
        text="Continue",
        stack_placement=StackPlacement(left=20.0, top=12.0, width=120.0, height=20.0),
    )
    return CleanDesignTreeNode(
        id="1:overlay_button",
        name="OverlayButton",
        type=NodeType.BUTTON,
        sizing=Sizing(width=200.0, height=44.0),
        children=[surface, label],
    )


def test_button_should_flow_as_column_detects_stacked_rows() -> None:
    assert button_should_flow_as_column(_order_card_button())
    assert not button_should_flow_as_column(_overlay_icon_button())


def test_stacked_row_button_body_emits_column_not_stack() -> None:
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=844.0),
        children=[_order_card_button()],
    )
    layout = render_layout_file(screen, feature_name="order_card", uses_svg=False)[
        "lib/generated/order_card_layout.dart"
    ]
    button_idx = layout.find("custom-code:figma-1_card_button:button-action")
    assert button_idx >= 0
    snippet = layout[max(0, button_idx - 400) : button_idx + 1800]
    assert "child: Column(mainAxisSize: MainAxisSize.min" in snippet
    assert "Row(mainAxisAlignment: MainAxisAlignment.spaceBetween" in snippet
    assert snippet.count("Row(mainAxisAlignment: MainAxisAlignment.start") >= 1
    assert "child: Stack(clipBehavior: Clip.none, fit: StackFit.loose" not in snippet


_HISTORY_FIXTURE = Path(
    r"e:/@dev/flutter-demo-project/ataev/.figma_debug/processed/history_layout.json"
)


@pytest.mark.skipif(not _HISTORY_FIXTURE.is_file(), reason="local ataev debug fixture")
def test_history_order_card_button_flows_as_column() -> None:
    raw = json.loads(_HISTORY_FIXTURE.read_text(encoding="utf-8"))
    screen = CleanDesignTreeNode.model_validate(raw["cleanTree"])
    layout = render_layout_file(screen, feature_name="history", uses_svg=False)[
        "lib/generated/history_layout.dart"
    ]
    idx = layout.find("custom-code:figma-281_16121:button-action")
    assert idx >= 0
    snippet = layout[max(0, idx - 400) : idx + 3200]
    assert "child: Column(mainAxisSize: MainAxisSize.min" in snippet
    assert "spacing: 16.0" in snippet or "SizedBox(height: 16" in snippet
    assert "child: Stack(clipBehavior: Clip.none, fit: StackFit.loose" not in snippet


def test_overlay_button_still_emits_stack() -> None:
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=844.0),
        children=[_overlay_icon_button()],
    )
    layout = render_layout_file(screen, feature_name="overlay_button", uses_svg=False)[
        "lib/generated/overlay_button_layout.dart"
    ]
    assert "child: Stack(clipBehavior: Clip.none" in layout
