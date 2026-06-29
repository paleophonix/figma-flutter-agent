"""Tests for constraints and absolute positioning in deterministic layout."""

import json
import re
from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets import (
    _apply_stack_position,
    _child_needs_positioned_bounds,
    _ensure_positioned_stack_bounds,
    _positioned_fields,
    render_node_body,
)
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


def test_absolute_auto_layout_child_preserves_bbox_offset_over_center_constraint() -> None:
    """Law: absolute_child_offset_preserved_over_constraint."""
    parent = {
        "id": "1:1",
        "name": "Content",
        "type": "FRAME",
        "layoutMode": "VERTICAL",
        "absoluteBoundingBox": {"x": 0.0, "y": 100.0, "width": 327.0, "height": 706.0},
        "children": [],
    }
    child = {
        "id": "1:2",
        "name": "Pattern",
        "type": "FRAME",
        "layoutPositioning": "ABSOLUTE",
        "constraints": {"vertical": "CENTER", "horizontal": "CENTER"},
        "absoluteBoundingBox": {"x": -5.0, "y": 62.0, "width": 375.0, "height": 257.0},
    }
    placement = extract_stack_placement(child, parent)
    assert placement is not None
    assert placement.top == -38.0
    assert placement.left == -5.0


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


def test_center_placement_emits_symmetric_left_right() -> None:
    """CENTER pins with both insets stay centered when the stack grows wider."""
    placement = StackPlacement(
        horizontal="CENTER",
        vertical="BOTTOM",
        left=113.5,
        right=113.0,
        bottom=8.0,
        width=148.0,
        height=5.0,
    )
    fields = ", ".join(_positioned_fields(placement))
    assert "left: 113.5" in fields
    assert "right: 113.0" in fields
    assert "bottom: 8.0" in fields
    assert "height: 5.0" in fields
    assert "width:" not in fields


def test_left_top_placement_emits_figma_width_and_height() -> None:
    placement = StackPlacement(
        horizontal="LEFT",
        vertical="TOP",
        left=20.0,
        top=228.0,
        width=374.0,
        height=63.0,
    )
    fields = ", ".join(_positioned_fields(placement))
    assert "left: 20.0" in fields
    assert "top: 228.0" in fields
    assert "width: 374.0" in fields
    assert "height: 63.0" in fields


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
    assert re.search(r"Positioned\(.*child:\s*Semantics\(", layout)
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
    assert "374.0" in layout and "63.0" in layout
    assert "BoxDecoration" in layout
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
        r"Positioned\(.*width: 200\.0.*height: 120\.0.*child: Stack\(",
        layout,
    )


def test_layout_root_stack_is_scrollable_with_design_viewport() -> None:
    root = json.loads(
        Path("tests/fixtures/figma_absolute_stack_sample.json").read_text(encoding="utf-8")
    )
    tree, _, _, _ = build_clean_tree(root)
    layout = render_layout_file(
        tree, feature_name="overlay", uses_svg=False, responsive_enabled=False
    )["lib/generated/overlay_layout.dart"]
    assert "SingleChildScrollView(" in layout
    assert "Center(child: Material(" in layout
    assert "SizedBox(width: 360.0, height: 640.0" in layout


def test_card_with_flat_children_gets_full_positioned_box() -> None:
    card = CleanDesignTreeNode(
        id="1:9001",
        name="Profile card",
        type=NodeType.CARD,
        sizing=Sizing(width=320.0, height=120.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=16.0,
            top=80.0,
            width=320.0,
            height=120.0,
        ),
        children=[
            CleanDesignTreeNode(id="1:9002", name="Avatar", type=NodeType.IMAGE),
            CleanDesignTreeNode(id="1:9003", name="Title", type=NodeType.TEXT, text="Nik"),
        ],
    )
    wrapped = _apply_stack_position(
        card,
        "Card(child: Column(children: [Text('Nik')]))",
        parent_type=NodeType.STACK,
    )
    assert "width: 320.0" in wrapped
    assert "height: 120.0" in wrapped


def test_container_with_nested_stack_gets_full_positioned_box() -> None:
    """Absolute hosts with explicit Figma frame size pin left/top/width/height."""
    button_group = CleanDesignTreeNode(
        id="1:3590",
        name="Google Button",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=374.0, height=69.0),
        stack_placement=StackPlacement(left=20.0, top=287.0),
        children=[
            CleanDesignTreeNode(
                id="1:3591",
                name="Inner",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="1:3592",
                        name="Label",
                        type=NodeType.TEXT,
                        text="Continue",
                    ),
                ],
            ),
        ],
    )
    inner_stack = render_node_body(
        button_group.children[0],
        uses_svg=False,
        parent_type=NodeType.CONTAINER,
        parent_node=button_group,
    )
    wrapped = _apply_stack_position(
        button_group,
        f"Material(child: InkWell(child: Container(child: {inner_stack})))",
        parent_type=NodeType.STACK,
    )

    assert _child_needs_positioned_bounds(button_group, wrapped)
    assert "width: 374.0" in wrapped
    assert "height: 69.0" in wrapped
    assert re.search(
        r"Positioned\([^)]*left: 20\.0[^)]*top: 287\.0[^)]*width: 374\.0[^)]*height: 69\.0",
        wrapped,
    )


def test_ensure_positioned_stack_bounds_preserves_bottom_anchor() -> None:
    node = CleanDesignTreeNode(
        id="1:1330",
        name="BottomNavBar",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=106.0),
        stack_placement=StackPlacement(
            vertical="BOTTOM",
            top=738.0,
            width=390.0,
            height=106.0,
        ),
    )
    placement = node.stack_placement
    assert placement is not None
    fields = _positioned_fields(placement, parent_height=844.0)
    _ensure_positioned_stack_bounds(fields, node, placement, parent_height=844.0)
    joined = ", ".join(fields)
    assert "bottom: 0.0" in joined
    assert "top:" not in joined


def test_ensure_positioned_stack_bounds_pins_full_box_for_nested_stack_container() -> None:
    node = CleanDesignTreeNode(
        id="1:10",
        name="Auth",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=300.0, height=48.0),
        children=[
            CleanDesignTreeNode(id="1:11", name="Inner", type=NodeType.STACK, children=[]),
        ],
    )
    placement = StackPlacement(left=16.0, top=8.0)
    fields = _positioned_fields(placement)
    _ensure_positioned_stack_bounds(fields, node, placement)
    joined = ", ".join(fields)
    assert "left: 16.0" in joined
    assert "top: 8.0" in joined
    assert "width: 300.0" in joined
    assert "height: 48.0" in joined
