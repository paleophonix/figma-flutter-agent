"""Emit-contract regressions (FID-06, FID-15, FID-19, FID-21, FID-22, FID-26)."""

from __future__ import annotations

from figma_flutter_agent.generator.emit_fidelity_audit import (
    audit_emit_contracts,
    count_emit_contract_gaps,
)
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.interaction import (
    input_children_are_presentational,
    looks_like_input_trailing_icon_button,
)
from figma_flutter_agent.parser.layout import (
    clamp_stack_child_placement_to_parent,
    reconcile_stack_placements_in_tree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    CornerRadii,
    NodeStyle,
    NodeType,
    ShadowEffect,
    Sizing,
    StackPlacement,
)


def test_clamp_stack_child_placement_to_parent_artboard() -> None:
    placement = StackPlacement(
        horizontal="LEFT_RIGHT",
        left=-20.0,
        right=-20.0,
        width=397.0,
        height=84.0,
        top=0.0,
    )
    clamped = clamp_stack_child_placement_to_parent(placement, 390.0)
    assert clamped.left == 0.0
    assert clamped.width == 390.0
    assert clamped.horizontal == "LEFT"


def test_reconcile_clamps_bleeding_header_in_tree() -> None:
    header = CleanDesignTreeNode(
        id="1:324",
        name="Header",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=397.0, height=84.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            left=-20.0,
            width=397.0,
            height=84.0,
        ),
        style=NodeStyle(background_color="0xFFFCFBF8", layer_blur=24.0),
    )
    root = CleanDesignTreeNode(
        id="1:319",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[header],
    )
    reconciled = reconcile_stack_placements_in_tree(root)
    child = reconciled.children[0]
    assert child.stack_placement is not None
    assert child.stack_placement.left == 0.0
    assert child.stack_placement.width == 390.0


def test_frosted_layer_blur_keeps_drop_shadow_outside_clip() -> None:
    bar = CleanDesignTreeNode(
        id="1:bar",
        name="BottomNavBar",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=106.0),
        stack_placement=StackPlacement(bottom=0.0, width=390.0, height=106.0, vertical="BOTTOM"),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            background_blur=20.0,
            border_radius_corners=CornerRadii(
                top_left=52.0,
                top_right=52.0,
                bottom_right=0.0,
                bottom_left=0.0,
            ),
            effects=[
                ShadowEffect(
                    kind="drop",
                    color="0x0F191C1D",
                    offset_x=0.0,
                    offset_y=-8.0,
                    blur=24.0,
                    spread=0.0,
                )
            ],
        ),
        children=[
            CleanDesignTreeNode(
                id="1:cta",
                name="Button",
                type=NodeType.BUTTON,
                text="Save",
            ),
        ],
    )
    body = render_node_body(bar, uses_svg=False, parent_type=NodeType.STACK)
    assert "DecoratedBox(decoration: BoxDecoration(boxShadow:" in body
    assert body.index("DecoratedBox") < body.index("ClipRRect")


def test_frosted_layer_blur_emits_backdrop_filter() -> None:
    bar = CleanDesignTreeNode(
        id="1:324",
        name="Header",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=84.0),
        style=NodeStyle(
            background_color="0xFFFCFBF8",
            layer_blur=24.0,
            border_radius=28.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:325",
                name="Title",
                type=NodeType.TEXT,
                text="Title",
            ),
        ],
    )
    body = render_node_body(bar, uses_svg=False)
    assert "BackdropFilter" in body
    assert "ImageFilter.blur" in body


def test_trailing_icon_detects_deep_vector_nesting() -> None:
    calendar = CleanDesignTreeNode(
        id="1:365",
        name="Button menu",
        type=NodeType.BUTTON,
        sizing=Sizing(width=18.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:366",
                name="image fill",
                type=NodeType.COLUMN,
                sizing=Sizing(width=18.0, height=18.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:367",
                        name="image",
                        type=NodeType.STACK,
                        sizing=Sizing(width=14.0, height=13.0),
                        children=[
                            CleanDesignTreeNode(
                                id="1:368",
                                name="Vector",
                                type=NodeType.VECTOR,
                                sizing=Sizing(width=11.0, height=12.0),
                                style=NodeStyle(has_stroke=True),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    assert looks_like_input_trailing_icon_button(calendar)


def test_flex_date_input_emits_text_field_with_fill() -> None:
    calendar = CleanDesignTreeNode(
        id="1:365",
        name="Button menu",
        type=NodeType.BUTTON,
        sizing=Sizing(width=18.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:366",
                name="image fill",
                type=NodeType.COLUMN,
                sizing=Sizing(width=18.0, height=18.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:367",
                        name="image",
                        type=NodeType.STACK,
                        sizing=Sizing(width=14.0, height=13.0),
                        children=[
                            CleanDesignTreeNode(
                                id="1:368",
                                name="Vector",
                                type=NodeType.VECTOR,
                                sizing=Sizing(width=11.0, height=12.0),
                                style=NodeStyle(has_stroke=True),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    field = CleanDesignTreeNode(
        id="1:356",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=317.0, height=52.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="1:357",
                name="Container",
                type=NodeType.ROW,
                sizing=Sizing(width=285.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:360",
                        name="value",
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
    assert input_children_are_presentational(field)
    body = render_node_body(field, uses_svg=False)
    assert "TextFormField" in body
    assert "0xFFF6F6F2" in body


def test_bottom_nav_pins_bottom_not_top() -> None:
    root = CleanDesignTreeNode(
        id="1:319",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:1330",
                name="BottomNavBar",
                type=NodeType.COLUMN,
                sizing=Sizing(width=390.0, height=106.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    vertical="BOTTOM",
                    top=738.0,
                    width=390.0,
                    height=106.0,
                ),
                style=NodeStyle(background_color="0xFFFFFFFF"),
                children=[],
            )
        ],
    )
    body = render_node_body(
        root.children[0],
        uses_svg=False,
        parent_type=NodeType.STACK,
        parent_node=root,
    )
    assert "bottom:" in body
    assert "top: 738.0" not in body


def test_root_viewport_expands_when_bottom_chrome_present() -> None:
    root = CleanDesignTreeNode(
        id="1:319",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:1330",
                name="BottomNavBar",
                type=NodeType.COLUMN,
                sizing=Sizing(width=390.0, height=106.0),
                stack_placement=StackPlacement(vertical="BOTTOM", top=738.0, height=106.0),
            )
        ],
    )
    body = render_node_body(root, uses_svg=False, is_layout_root=True)
    assert "LayoutBuilder" in body
    assert "viewportHeight" in body
    assert ": 844.0" in body
    assert ": 844;" not in body
    assert "FittedBox" in body
    assert "BoxFit.scaleDown" in body
    assert "SingleChildScrollView" not in body


def test_bottom_chrome_layout_emits_parseable_dart() -> None:
    import pytest

    from figma_flutter_agent.dev.flutter_sdk import resolve_dart_executable
    from figma_flutter_agent.generator.dart.project_validation import gate_planned_dart_syntax
    from figma_flutter_agent.generator.layout import render_layout_file

    if resolve_dart_executable() is None:
        pytest.skip("dart SDK not available")

    root = CleanDesignTreeNode(
        id="1:319",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        style=NodeStyle(background_color="0xFFFCFBF8"),
        children=[
            CleanDesignTreeNode(
                id="1:1",
                name="Main",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=390.0, height=700.0),
            ),
            CleanDesignTreeNode(
                id="1:1330",
                name="BottomNavBar",
                type=NodeType.COLUMN,
                sizing=Sizing(width=390.0, height=106.0),
                stack_placement=StackPlacement(vertical="BOTTOM", top=738.0, height=106.0),
            ),
        ],
    )
    planned = render_layout_file(
        root,
        skip_layout_reconcile=True,
        feature_name="background",
        uses_svg=False,
        responsive_enabled=False,
    )
    outcome = gate_planned_dart_syntax(
        planned,
        package_name="demo_app",
        require_dart_sdk=True,
    )
    assert outcome.passed, outcome.errors
    layout = planned["lib/generated/background_layout.dart"]
    assert "return Align" in layout
    assert "),),})," not in layout.replace(" ", "")


def test_emit_contract_audit_counts_bottom_pin_regression() -> None:
    root = CleanDesignTreeNode(
        id="1:319",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="1:1330",
                name="BottomNavBar",
                type=NodeType.COLUMN,
                stack_placement=StackPlacement(vertical="BOTTOM", top=738.0, height=106.0),
            )
        ],
    )
    bad_emit = (
        "Positioned(left: 0.0, top: 738.0, height: 106.0, "
        "key: ValueKey('figma-1_1330'), child: const SizedBox())"
    )
    gaps = count_emit_contract_gaps(root, bad_emit, viewport_height=844.0)
    assert gaps.get("bottom_pin_used_top", 0) >= 1
    good_emit = (
        "Positioned(left: 0.0, bottom: 0.0, height: 106.0, "
        "key: ValueKey('figma-1_1330'), child: const SizedBox())"
    )
    assert not audit_emit_contracts(root, good_emit, viewport_height=844.0)


def test_emit_contract_audit_flags_vector_missing_export() -> None:
    vector = CleanDesignTreeNode(
        id="v1",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=8.0, height=8.0),
        style=NodeStyle(background_color="0xFF4285F4"),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=8.0, height=8.0),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        children=[vector],
    )
    from figma_flutter_agent.generator.layout import render_layout_file

    layout = render_layout_file(root, feature_name="vector_leaf", uses_svg=False)[
        "lib/generated/vector_leaf_layout.dart"
    ]
    violations = audit_emit_contracts(root, layout)
    assert any(
        item.code == "vector_missing_export" and item.node_id == "v1"
        for item in violations
    )
    gaps = count_emit_contract_gaps(root, layout)
    assert gaps.get("vector_missing_export", 0) >= 1


def test_chevron_fallback_uses_readable_size() -> None:
    back = CleanDesignTreeNode(
        id="1:327",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=48.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:329",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=5.0, height=10.0),
                style=NodeStyle(has_stroke=True, border_color="0xFF52525C"),
            )
        ],
    )
    body = render_node_body(back, uses_svg=False)
    assert "chevron_left" in body
    assert "size: 24.0" in body or "size: 24," in body
