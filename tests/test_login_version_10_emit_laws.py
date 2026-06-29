"""Regression laws converging on auth-card screens (login_version_10 family)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.background import partition_wallpaper_foreground_tree
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.file_methods import _tree_depth, plan_layout_methods
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.components import validate_semantic_type_for_node
from figma_flutter_agent.parser.interaction.buttons import (
    button_hosts_horizontal_social_auth_icon_cluster,
    button_hosts_multiple_auth_rows,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    LayoutSlotIr,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
    StackPlacement,
)


def _load_processed_root() -> CleanDesignTreeNode:
    processed = json.loads(
        Path(".debug/screen/limbo/login_version_10/processed.json").read_text(encoding="utf-8")
    )
    return CleanDesignTreeNode.model_validate(processed["cleanTree"])


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _layout_chunk_for_node(layout: str, figma_token: str) -> str:
    compact = layout.replace("\n", "")
    idx = compact.find(f"figma-{figma_token}")
    assert idx >= 0, f"missing figma-{figma_token} in layout"
    return compact[idx : idx + 25000]


def _deep_form_body(depth: int) -> CleanDesignTreeNode:
    node = CleanDesignTreeNode(
        id="leaf",
        name="Login",
        type=NodeType.TEXT,
        text="Login",
    )
    for index in range(depth - 1):
        node = CleanDesignTreeNode(
            id=f"n{index}",
            name=f"Level{index}",
            type=NodeType.COLUMN,
            sizing=Sizing(width=100.0, height=100.0),
            children=[node],
        )
    return node


def _ambient_wallpaper_ellipse(node_id: str, name: str) -> CleanDesignTreeNode:
    stem = node_id.replace(":", "_")
    return CleanDesignTreeNode(
        id=node_id,
        name=name,
        type=NodeType.VECTOR,
        sizing=Sizing(width=934.0, height=934.0),
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=27.0, top=419.0, width=934.0, height=934.0),
        vector_asset_key=f"assets/icons/{stem}.svg",
        image_asset_key=f"assets/images/{stem}.png",
        style=NodeStyle(background_color="0xFFB49EF4"),
    )


def _icon_only_social_row(row_id: str, *, left: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=row_id,
        name="Another Step login",
        type=NodeType.ROW,
        padding=Padding(top=10.0, bottom=10.0, left=24.0, right=24.0),
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=62.5,
            height=48.0,
        ),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFEFF0F6",
            border_radius=10.0,
        ),
        stack_placement=StackPlacement(left=left, top=0.0, width=62.5, height=48.0),
        children=[
            CleanDesignTreeNode(
                id=f"{row_id}:icon",
                name="Icon",
                type=NodeType.VECTOR,
                sizing=Sizing(width=18.0, height=18.0),
            ),
        ],
    )


def test_positioned_slot_caps_min_height_above_placement() -> None:
    """Law: positioned_slot_must_not_pin_min_height_above_placement_cap."""
    host = CleanDesignTreeNode(
        id="55:card",
        name="Input",
        type=NodeType.INPUT,
        spacing=24.0,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=343.0,
            height=905.5,
        ),
        stack_placement=StackPlacement(
            vertical="CENTER",
            left=16.0,
            top=125.5,
            width=343.0,
            height=561.0,
        ),
        layout_slot=LayoutSlotIr(min_height=905.5, max_height=905.5),
        children=[
            CleanDesignTreeNode(
                id="55:title",
                name="Login",
                type=NodeType.TEXT,
                text="Login",
            ),
            CleanDesignTreeNode(
                id="55:cta",
                name="Log In",
                type=NodeType.BUTTON,
                sizing=Sizing(width=295.0, height=48.0),
                children=[
                    CleanDesignTreeNode(
                        id="55:cta-label",
                        name="Log In",
                        type=NodeType.TEXT,
                        text="Log In",
                    ),
                ],
            ),
        ],
    )
    body = render_node_body(
        host,
        uses_svg=False,
        parent_type=NodeType.STACK,
        parent_node=CleanDesignTreeNode(
            id="53:root",
            name="Screen",
            type=NodeType.STACK,
            sizing=Sizing(width=375.0, height=812.0),
        ),
    )
    compact = body.replace("\n", "")
    assert "height: 561.0" in compact
    assert "minHeight: 905.5" not in compact
    assert "maxHeight: 905.5" not in compact
    assert "OverflowBox(" in compact


def test_named_input_frame_with_children_is_not_leaf_input() -> None:
    """Law: leaf_type_is_structural_not_name."""
    raw = {
        "id": "55:2044",
        "name": "Input",
        "type": "FRAME",
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 343, "height": 905},
        "children": [
            {"id": "a", "name": "Title", "type": "TEXT"},
            {"id": "b", "name": "Field", "type": "FRAME"},
        ],
    }
    assert validate_semantic_type_for_node(raw, NodeType.INPUT) is False


def test_horizontal_icon_only_social_cluster_emits_row() -> None:
    """Law: social_auth_icon_only_cluster_must_emit_horizontal_row."""
    host = CleanDesignTreeNode(
        id="56:2102",
        name="Button",
        type=NodeType.BUTTON,
        spacing=15.0,
        sizing=Sizing(width=295.0, height=48.0),
        children=[
            _icon_only_social_row("56:2103", left=0.0),
            _icon_only_social_row("56:2104", left=77.5),
            _icon_only_social_row("56:2105", left=155.0),
            _icon_only_social_row("56:2106", left=232.5),
        ],
    )
    assert button_hosts_multiple_auth_rows(host)
    assert button_hosts_horizontal_social_auth_icon_cluster(host)
    body = render_node_body(host, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Row(" in compact
    assert "spacing: 15.0" in compact
    assert compact.count("InkWell(") >= 4
    assert "Stack(fit: StackFit.loose" not in compact


def test_decomposed_wallpaper_stack_root_preview_is_bounded() -> None:
    """Law: stack_root_requires_finite_bounds for wallpaper-partitioned auth shells."""
    root = CleanDesignTreeNode(
        id="53:1896",
        name="Login Version 10",
        type=NodeType.STACK,
        style=NodeStyle(background_color="0xFFFFFFFF"),
        sizing=Sizing(width=375.0, height=812.0),
        children=[
            _ambient_wallpaper_ellipse("54:2043", "Ellipse 2"),
            _ambient_wallpaper_ellipse("54:2042", "Ellipse 1"),
            CleanDesignTreeNode(
                id="55:2044",
                name="Input",
                type=NodeType.STACK,
                spacing=24.0,
                sizing=Sizing(width=343.0, height=561.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    left=16.0,
                    top=125.5,
                    width=343.0,
                    height=561.0,
                ),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_radius=12.0,
                    border_color="0xFFFFFFFF",
                ),
                children=[_deep_form_body(8)],
            ),
            CleanDesignTreeNode(
                id="53:1983",
                name="Native / Status Bar",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=44.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="53:1984",
                name="Native / Home Indicator",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=34.0),
                children=[],
            ),
        ],
    )
    layout = render_layout_file(
        root,
        feature_name="login_wallpaper_shell",
        uses_svg=False,
        responsive_enabled=True,
    )["lib/generated/login_wallpaper_shell_layout.dart"]
    assert "maxHeight: double.infinity" not in layout
    assert "Stack(clipBehavior:" in layout
    preview_section = layout.split("_artboardPreviewHeight", 1)[0]
    assert "OverflowBox(" not in preview_section or "maxHeight: previewH" in layout


def test_decomposed_layout_paints_partitioned_wallpaper() -> None:
    """Law: partitioned_wallpaper_is_painted."""
    root = CleanDesignTreeNode(
        id="53:1896",
        name="Login Version 10",
        type=NodeType.STACK,
        style=NodeStyle(background_color="0xFFFFFFFF"),
        sizing=Sizing(width=375.0, height=812.0),
        children=[
            _ambient_wallpaper_ellipse("54:2043", "Ellipse 2"),
            _ambient_wallpaper_ellipse("54:2042", "Ellipse 1"),
            CleanDesignTreeNode(
                id="55:2044",
                name="Input",
                type=NodeType.STACK,
                spacing=24.0,
                sizing=Sizing(width=343.0, height=561.0),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    left=16.0,
                    top=125.5,
                    width=343.0,
                    height=561.0,
                ),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_radius=12.0,
                    border_color="0xFFFFFFFF",
                ),
                children=[_deep_form_body(8)],
            ),
            CleanDesignTreeNode(
                id="53:1983",
                name="Native / Status Bar",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=44.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="53:1984",
                name="Native / Home Indicator",
                type=NodeType.STACK,
                sizing=Sizing(width=375.0, height=34.0),
                children=[],
            ),
        ],
    )
    assert _tree_depth(root) > 7
    render_tree, wallpaper_children, shell_color = partition_wallpaper_foreground_tree(root)
    assert len(wallpaper_children) == 2
    assert shell_color is None
    methods = plan_layout_methods(render_tree)
    assert methods is not None
    layout = render_layout_file(root, feature_name="login_wallpaper_shell", uses_svg=False)[
        "lib/generated/login_wallpaper_shell_layout.dart"
    ]
    assert "Positioned.fill(" in layout
    assert "FittedBox(" in layout
    assert "color: Color(0xFFFFFFFF)" not in layout.split("Stack(clipBehavior: Clip.none")[0]


def test_login_version_10_card_stack_emits_coalesced_inflow_column() -> None:
    """Law: stack_inflow_children_must_emit_under_flow_parent_not_bare_stack_siblings."""
    root = _load_processed_root()
    layout = render_layout_file(root, feature_name="login_version_10", uses_svg=False)[
        "lib/generated/login_version_10_layout.dart"
    ]
    card = _find_node(root, "55:2044")
    assert card is not None
    chunk = _layout_chunk_for_node(layout, "55_2044")
    assert "crossAxisAlignment: CrossAxisAlignment.stretch, spacing: 24.0" in chunk
    assert "Login" in chunk
    assert "Log In" in chunk
    assert "Loisbecket@gmail.com" in chunk
    assert "Or login with" in chunk


def test_login_version_10_card_stack_emits_surface_decoration() -> None:
    """Law: styled_stack_host_must_emit_surface_decoration."""
    root = _load_processed_root()
    layout = render_layout_file(root, feature_name="login_version_10", uses_svg=False)[
        "lib/generated/login_version_10_layout.dart"
    ]
    chunk = _layout_chunk_for_node(layout, "55_2044")
    assert "Container(decoration: BoxDecoration(" in chunk
    assert "borderRadius: BorderRadius.circular(12.0)" in chunk


def test_login_version_10_buttons_column_not_inline_text_field() -> None:
    """Law: inline_input_host_requires_exclusive_label_and_surface_children."""
    root = _load_processed_root()
    layout = render_layout_file(root, feature_name="login_version_10", uses_svg=False)[
        "lib/generated/login_version_10_layout.dart"
    ]
    assert "initialValue: 'Log In'" not in layout
    assert "initialValue: 'Get Started'" not in layout
    assert "InkWell(" in layout
    assert "Or login with" in layout
    assert "56_2104" in layout


def test_inline_labeled_input_host_rejects_extra_column_children() -> None:
    """Law: inline_input_host_requires_exclusive_label_and_surface_children."""
    from figma_flutter_agent.parser.interaction.inline_input_hosts import (
        layout_fact_inline_labeled_input_field_host,
    )

    label = CleanDesignTreeNode(
        id="col:label",
        name="Email",
        type=NodeType.TEXT,
        text="Email",
    )
    surface = CleanDesignTreeNode(
        id="col:surface",
        name="Input area",
        type=NodeType.ROW,
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFEDF1F3",
            border_radius=10.0,
        ),
        children=[],
    )
    button = CleanDesignTreeNode(
        id="col:cta",
        name="Log In",
        type=NodeType.BUTTON,
        children=[],
    )
    host = CleanDesignTreeNode(
        id="col:host",
        name="Buttons",
        type=NodeType.COLUMN,
        children=[surface, label, button],
    )
    assert layout_fact_inline_labeled_input_field_host(host) is False


def test_decorative_blur_absolute_does_not_block_mixed_inflow() -> None:
    """Law: decorative_absolute_raster_must_not_block_mixed_inflow_column."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_has_non_sequential_raster_overlay,
        stack_should_emit_mixed_inflow_column_overlay,
    )

    root = _load_processed_root()
    card = _find_node(root, "55:2044")
    assert card is not None
    assert stack_has_non_sequential_raster_overlay(card) is False
    assert stack_should_emit_mixed_inflow_column_overlay(card) is True
