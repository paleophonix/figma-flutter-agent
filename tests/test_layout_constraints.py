"""Tests for constraints and absolute positioning in deterministic layout."""

import json
import re
from pathlib import Path

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.layout_widget import _positioned_fields
from figma_flutter_agent.parser.layout import extract_stack_placement
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_absolute_child_in_stack_renders_positioned() -> None:
    root = json.loads(
        Path("tests/fixtures/figma_absolute_stack_sample.json").read_text(encoding="utf-8")
    )
    tree, _, _, _ = build_clean_tree(root)
    layout = render_layout_file(tree, feature_name="overlay", uses_svg=False)[
        "lib/generated/overlay_layout.dart"
    ]

    assert "Stack(" in layout
    assert "Positioned(" in layout
    assert "left: 24.0" in layout or "left: 24," in layout
    assert "top: 48.0" in layout or "top: 48," in layout
    assert "Text('New'" in layout


def test_fill_width_in_row_uses_expanded_not_in_column() -> None:
    row_child = CleanDesignTreeNode(
        id="2",
        name="Fill",
        type=NodeType.TEXT,
        text="Wide",
        sizing=Sizing(width_mode=SizingMode.FILL),
    )
    row_tree = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        children=[row_child],
    )
    column_child = CleanDesignTreeNode(
        id="4",
        name="Fill",
        type=NodeType.TEXT,
        text="Tall",
        sizing=Sizing(height_mode=SizingMode.FILL),
    )
    column_tree = CleanDesignTreeNode(
        id="3",
        name="Column",
        type=NodeType.COLUMN,
        children=[column_child],
    )

    row_layout = render_layout_file(row_tree, feature_name="row", uses_svg=False)[
        "lib/generated/row_layout.dart"
    ]
    column_layout = render_layout_file(column_tree, feature_name="column", uses_svg=False)[
        "lib/generated/column_layout.dart"
    ]

    assert "Expanded(child:" in row_layout
    assert "Expanded(child:" in column_layout
    assert row_layout.count("Expanded(child:") == 1


def test_classic_right_bottom_constraints_render_positioned_edges() -> None:
    root = json.loads(
        Path("tests/fixtures/figma_constraints_right_bottom_sample.json").read_text(
            encoding="utf-8"
        )
    )
    parent = root
    child = root["children"][0]
    placement = extract_stack_placement(child, parent)
    assert placement is not None
    assert placement.horizontal == "RIGHT"
    assert placement.vertical == "BOTTOM"
    assert placement.right == 24.0
    assert placement.bottom == 16.0

    tree, _, _, _ = build_clean_tree(root)
    layout = render_layout_file(tree, feature_name="anchored", uses_svg=False)[
        "lib/generated/anchored_layout.dart"
    ]

    assert "Positioned(right: 24.0, bottom: 16.0" in layout
    assert "Text('Save'" in layout


def test_left_right_constraint_renders_horizontal_pin() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Bar",
        type=NodeType.TEXT,
        text="Bar",
        stack_placement=StackPlacement(horizontal="LEFT_RIGHT", left=8, right=8, top=4),
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[child],
    )

    layout = render_layout_file(parent, feature_name="pinned", uses_svg=False)[
        "lib/generated/pinned_layout.dart"
    ]

    assert "Positioned(left: 8.0, right: 8.0, top: 4.0" in layout
    assert "width:" not in layout.split("Positioned(", 1)[1].split("child:", 1)[0]


def test_left_right_stretch_skips_redundant_positioned_width() -> None:
    """``LEFT_RIGHT`` stretch must not also pin ``width`` (invalid Positioned)."""
    inner = CleanDesignTreeNode(
        id="3",
        name="Inner",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=120.0),
        children=[
            CleanDesignTreeNode(id="4", name="Label", type=NodeType.TEXT, text="Hi"),
        ],
    )
    child = CleanDesignTreeNode(
        id="2",
        name="Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=120.0),
        stack_placement=StackPlacement(
            horizontal="LEFT_RIGHT",
            vertical="TOP",
            left=8,
            right=8,
            top=4,
        ),
        children=[inner],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[child],
    )
    layout = render_layout_file(parent, feature_name="stretch", uses_svg=False)[
        "lib/generated/stretch_layout.dart"
    ]
    positioned_args = layout.split("Positioned(", 1)[1].split("child:", 1)[0]
    assert "left:" in positioned_args
    assert "right:" in positioned_args
    assert "width:" not in positioned_args


def test_scale_constraint_uses_width_not_left_right_width() -> None:
    """SCALE must not emit left+right+width (invalid Positioned)."""
    placement = StackPlacement(
        horizontal="SCALE",
        vertical="SCALE",
        left=10.0,
        right=20.0,
        top=5.0,
        bottom=15.0,
        width=100.0,
        height=50.0,
    )
    fields = ", ".join(_positioned_fields(placement))
    assert "left: 10.0" in fields
    assert "width: 100.0" in fields
    assert "right:" not in fields
    assert "top: 5.0" in fields
    assert "height: 50.0" in fields
    assert "bottom:" not in fields


def test_stack_semantics_is_child_of_positioned_not_parent() -> None:
    """``Positioned`` must be a direct child of ``Stack`` (not wrapped by ``Semantics``)."""
    child = CleanDesignTreeNode(
        id="2",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/icon.svg",
        accessibility_label="Vector",
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=8, top=4),
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[child],
    )
    layout = render_layout_file(parent, feature_name="stack_a11y", uses_svg=True)[
        "lib/generated/stack_a11y_layout.dart"
    ]
    assert re.search(r"Positioned\([^)]*child:\s*Semantics\(", layout)
    assert not re.search(r"Semantics\([^)]*child:\s*Positioned\(", layout)


def test_filled_rectangle_renders_container_not_shrink() -> None:
    """Figma RECTANGLE leaves with solid fills must paint a surface (buttons, cards)."""
    button_bg = CleanDesignTreeNode(
        id="2",
        name="Rectangle 210",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=63.0),
        style=NodeStyle(background_color="0xFF8E97FD", border_radius=38.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=0, top=0),
    )
    label = CleanDesignTreeNode(
        id="3",
        name="LOG IN",
        type=NodeType.TEXT,
        text="LOG IN",
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=161, top=24.5),
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=63.0),
        stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=20, top=620),
        children=[button_bg, label],
    )
    screen = CleanDesignTreeNode(
        id="0",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[parent],
    )
    layout = render_layout_file(screen, feature_name="login", uses_svg=False)[
        "lib/generated/login_layout.dart"
    ]
    assert "SizedBox.shrink()" not in layout or layout.count("SizedBox.shrink()") <= 1
    assert "Container(width: 374.0, height: 63.0, decoration: BoxDecoration" in layout
    assert "Text('LOG IN'" in layout


def test_nested_stack_in_positioned_gets_bounded_size() -> None:
    """Inner ``Stack`` inside ``Positioned`` must receive width/height pins."""
    inner = CleanDesignTreeNode(
        id="3",
        name="Inner",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=120.0),
        children=[
            CleanDesignTreeNode(
                id="4",
                name="Label",
                type=NodeType.TEXT,
                text="Hi",
            )
        ],
    )
    outer = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=360.0, height=640.0),
        children=[
            CleanDesignTreeNode(
                id="2",
                name="Group",
                type=NodeType.STACK,
                sizing=Sizing(width=200.0, height=120.0),
                stack_placement=StackPlacement(horizontal="LEFT", vertical="TOP", left=8, top=4),
                children=[inner],
            )
        ],
    )
    layout = render_layout_file(outer, feature_name="nested_stack", uses_svg=False)[
        "lib/generated/nested_stack_layout.dart"
    ]
    assert re.search(
        r"Positioned\([^)]*width: 200\.0[^)]*height: 120\.0[^)]*child: Stack\(",
        layout,
    )


def test_layout_root_stack_is_scrollable_with_design_viewport() -> None:
    root = json.loads(
        Path("tests/fixtures/figma_absolute_stack_sample.json").read_text(encoding="utf-8")
    )
    tree, _, _, _ = build_clean_tree(root)
    layout = render_layout_file(tree, feature_name="overlay", uses_svg=False)[
        "lib/generated/overlay_layout.dart"
    ]
    assert "SingleChildScrollView(" in layout
    assert "Center(child: Material(" in layout
    assert "SizedBox(width: 360.0, height: 640.0" in layout
