"""Regression laws converging on auth-card screens (login_version_10 family)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.background import partition_wallpaper_foreground_tree
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.file_methods import _tree_depth, plan_layout_methods
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.components import validate_semantic_type_for_node
from figma_flutter_agent.parser.interaction import list_tile_leading_icon_slot
from figma_flutter_agent.parser.interaction.buttons import (
    button_hosts_horizontal_social_auth_icon_cluster,
    button_hosts_multiple_auth_rows,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GradientFill,
    GradientStop,
    LayoutSlotIr,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
    StackPlacement,
)


def _load_processed_root() -> CleanDesignTreeNode:
    path = Path(".debug/screen/limbo/login_version_10/processed.json")
    if not path.is_file():
        pytest.skip("login_version_10 debug dumps not available")
    processed = json.loads(path.read_text(encoding="utf-8"))
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
            width_mode=SizingMode.FILL,
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


def test_list_tile_leading_icon_does_not_double_wrap_dart_color_expr() -> None:
    """Law: dart_color_expr_must_not_be_double_wrapped_in_color_constructor."""
    from figma_flutter_agent.generator.layout.widgets.emit.containers import render_misc

    node = CleanDesignTreeNode(
        id="social:chip",
        name="Another Step login",
        type=NodeType.ROW,
        sizing=Sizing(width=62.5, height=48.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=10.0),
        vector_asset_key="assets/icons/google.svg",
    )
    body = render_misc.list_tile_leading_icon(
        node,
        parent_node=None,
        uses_svg=True,
        cluster_id=None,
        cluster_vector_variants=None,
        parent_type=NodeType.ROW,
    )
    assert "Color(Color(" not in body
    assert "color: Color(0xFFFFFFFF)" in body


def test_social_auth_icon_chip_rejects_list_tile_leading_icon_slot() -> None:
    """Law: social_auth_icon_chip_must_not_route_through_list_tile_leading_icon_slot."""
    host = CleanDesignTreeNode(
        id="56:2102",
        name="Button",
        type=NodeType.ROW,
        spacing=15.0,
        sizing=Sizing(width=295.0, height=48.0),
        children=[
            _icon_only_social_row("56:2103", left=0.0),
            _icon_only_social_row("56:2104", left=77.5),
            _icon_only_social_row("56:2105", left=155.0),
            _icon_only_social_row("56:2106", left=232.5),
        ],
    )
    assert button_hosts_horizontal_social_auth_icon_cluster(host)
    chip = host.children[0]
    assert not list_tile_leading_icon_slot(chip, host, parent_type=NodeType.ROW)


def test_login_input_widget_emit_has_no_double_color_wrap() -> None:
    """Law: dart_color_expr_must_not_be_double_wrapped_in_color_constructor (subtree)."""
    root = _load_processed_root()
    layout = render_layout_file(root, feature_name="login_version_10_color", uses_svg=True)[
        "lib/generated/login_version_10_color_layout.dart"
    ]
    assert "Color(Color(" not in layout


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
    assert "_buildBackground" in layout
    assert "54_2043" in layout
    assert "Image.asset(" in layout or "ImageFiltered(" in layout


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


def _synthetic_bounded_card_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="card:host",
        name="Input",
        type=NodeType.STACK,
        padding=Padding(top=24.0, bottom=24.0, left=24.0, right=24.0),
        spacing=24.0,
        sizing=Sizing(width=343.0, height=561.0),
        style=NodeStyle(
            background_color="0x99FFFFFF",
            border_radius=12.0,
            border_color="0x99FFFFFF",
            border_width=1.0,
            has_stroke=True,
            clips_content=True,
        ),
        children=[
            CleanDesignTreeNode(
                id="card:logo",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=34.0, height=34.0),
                vector_asset_key="assets/icons/vector_card_logo.svg",
                style=NodeStyle(
                    gradient=GradientFill(
                        type="linear",
                        stops=[
                            GradientStop(position=0.0, color="0xFF6E8AFC"),
                            GradientStop(position=1.0, color="0xFF375DFB"),
                        ],
                        angle=90.0,
                    ),
                ),
            ),
            CleanDesignTreeNode(
                id="card:heading",
                name="Login",
                type=NodeType.TEXT,
                text="Login",
                sizing=Sizing(width=85.0, height=42.0),
            ),
            CleanDesignTreeNode(
                id="card:field",
                name="Email",
                type=NodeType.INPUT,
                sizing=Sizing(width=295.0, height=46.0),
                children=[],
            ),
            CleanDesignTreeNode(
                id="card:blur",
                name="Ellipse 1",
                type=NodeType.VECTOR,
                sizing=Sizing(width=320.5, height=320.5),
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(
                    left=192.0,
                    top=-170.5,
                    width=320.5,
                    height=320.5,
                ),
                vector_asset_key="assets/icons/ellipse_card_blur.svg",
                image_asset_key="assets/images/ellipse_card_blur.png",
                style=NodeStyle(layer_blur=130.0),
            ),
        ],
    )


def test_login_card_surface_emits_translucent_fill_and_padding() -> None:
    """Law: solid_fill_paint_opacity + autolayout_stack_surface_must_apply_padding."""
    root = _synthetic_bounded_card_stack()
    layout = render_layout_file(root, feature_name="login_card_surface", uses_svg=True)[
        "lib/generated/login_card_surface_layout.dart"
    ]
    assert "Color(0x99FFFFFF)" in layout
    assert "EdgeInsets.fromLTRB(24.0, 24.0, 24.0, 24.0)" in layout
    assert "Container(decoration: BoxDecoration(" in layout


def test_login_card_clips_decorative_children_to_radius() -> None:
    """Law: clips_content_surface_must_clip_children_to_border_radius."""
    root = _synthetic_bounded_card_stack()
    layout = render_layout_file(root, feature_name="login_card_clip", uses_svg=True)[
        "lib/generated/login_card_clip_layout.dart"
    ]
    assert "ClipRRect(borderRadius: BorderRadius.circular(12.0)" in layout


def test_login_version_10_processed_card_emits_padding() -> None:
    """Law: autolayout_stack_surface_must_apply_padding_to_painted_children."""
    root = _load_processed_root()
    layout = render_layout_file(root, feature_name="login_version_10_padding", uses_svg=True)[
        "lib/generated/login_version_10_padding_layout.dart"
    ]
    assert "EdgeInsets.fromLTRB(24.0, 24.0, 24.0, 24.0)" in layout


def test_login_version_10_processed_logo_uses_contain_fit() -> None:
    """Law: vector_brand_glyph_must_preserve_intrinsic_aspect_ratio."""
    root = _load_processed_root()
    layout = render_layout_file(root, feature_name="login_version_10_logo", uses_svg=True)[
        "lib/generated/login_version_10_logo_layout.dart"
    ]
    assert "vector_55_2096.svg" in layout
    assert "fit: BoxFit.contain" in layout or "fit: BoxFit.scaleDown" in layout
    assert "vector_55_2096.svg', width: 34.0, height: 34.0, fit: BoxFit.fill" not in layout


def test_login_card_in_card_blur_not_hoisted_to_wallpaper() -> None:
    """Law: in_card_decorative_absolute_must_paint_behind_inflow_without_wallpaper_duplicate."""
    from figma_flutter_agent.generator.background import extract_nested_decorative_backgrounds

    root = _synthetic_bounded_card_stack()
    _, extracted = extract_nested_decorative_backgrounds(root)
    assert not any(node.id == "card:blur" for node in extracted)
    _, wallpaper_children, _ = partition_wallpaper_foreground_tree(root)
    assert not any(child.id == "card:blur" for child in wallpaper_children)


def test_login_card_logo_vector_uses_contain_fit() -> None:
    """Law: vector_brand_glyph_must_preserve_intrinsic_aspect_ratio."""
    root = _synthetic_bounded_card_stack()
    layout = render_layout_file(root, feature_name="login_card_logo", uses_svg=True)[
        "lib/generated/login_card_logo_layout.dart"
    ]
    assert "vector_card_logo.svg" in layout
    assert "fit: BoxFit.contain" in layout
    assert "vector_card_logo.svg', width: 34.0, height: 34.0, fit: BoxFit.fill" not in layout


def test_login_version_10_in_card_blur_not_duplicated_on_wallpaper() -> None:
    """Law: in_card_decorative_absolute_must_paint_behind_inflow_without_wallpaper_duplicate."""
    root = _load_processed_root()
    _, wallpaper_children, _ = partition_wallpaper_foreground_tree(root)
    wallpaper_ids = {child.id for child in wallpaper_children}
    assert "56:2126" not in wallpaper_ids
    layout = render_layout_file(root, feature_name="login_version_10_wallpaper", uses_svg=True)[
        "lib/generated/login_version_10_wallpaper_layout.dart"
    ]
    bg = layout.split("Widget _buildBackground")[1][:2500] if "_buildBackground" in layout else ""
    if bg:
        assert "figma-56_2126" not in bg


def _single_surface_input_field_column() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="55:2051",
        name="Input Field",
        type=NodeType.COLUMN,
        spacing=2.0,
        sizing=Sizing(width=295.0, height=46.0),
        children=[
            CleanDesignTreeNode(
                id="I55:2051;3:6011",
                name="Input Area",
                type=NodeType.ROW,
                padding=Padding(top=11.5, bottom=11.5, left=13.0, right=13.0),
                sizing=Sizing(width=295.0, height=46.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_color="0xFFEDF1F3",
                    border_radius=10.0,
                    border_width=1.0,
                ),
                children=[
                    CleanDesignTreeNode(
                        id="I55:2051;3:6014",
                        name="Value",
                        type=NodeType.TEXT,
                        text="Loisbecket@gmail.com",
                        sizing=Sizing(width=207.0, height=21.0),
                    ),
                ],
            ),
        ],
    )


def test_single_surface_input_field_column_emits_text_form_field() -> None:
    """Law: input_text_field_contract_must_emit_text_form_field_not_static_container."""
    from figma_flutter_agent.parser.interaction.inline_input_hosts import (
        layout_fact_single_surface_input_field_column,
    )

    node = _single_surface_input_field_column()
    assert layout_fact_single_surface_input_field_column(node)
    body = render_node_body(node, uses_svg=False)
    compact = body.replace("\n", "")
    assert "TextFormField(" in compact
    assert "initialValue: 'Loisbecket@gmail.com'" in compact
    assert "Text('Loisbecket@gmail.com'" not in compact


def test_row_social_auth_cluster_wraps_inkwell_per_child() -> None:
    """Law: social_login_button_surface_must_be_clickable."""
    host = CleanDesignTreeNode(
        id="56:2102",
        name="Button",
        type=NodeType.ROW,
        spacing=15.0,
        sizing=Sizing(width=295.0, height=48.0),
        children=[
            _icon_only_social_row("56:2103", left=0.0),
            _icon_only_social_row("56:2104", left=77.5),
            _icon_only_social_row("56:2105", left=155.0),
            _icon_only_social_row("56:2106", left=232.5),
        ],
    )
    body = render_node_body(host, uses_svg=False)
    compact = body.replace("\n", "")
    assert compact.count("InkWell(") >= 4


def _assert_inkwell_hosts_no_flex_parent_data(compact: str) -> None:
    """Fail when an ``InkWell``/``GestureDetector`` directly hosts ``Expanded``/``Flexible``."""
    markers = ("InkWell(", "GestureDetector(")
    for marker in markers:
        index = 0
        while True:
            start = compact.find(marker, index)
            if start < 0:
                break
            window = compact[start : start + 500]
            assert "child: Expanded(" not in window
            assert "child: Flexible(" not in window
            index = start + len(marker)


def test_social_auth_row_children_must_be_finite_flex_children() -> None:
    """Law: social_button_row_children_must_be_finite_flex_children."""
    host = CleanDesignTreeNode(
        id="56:2102",
        name="Button",
        type=NodeType.ROW,
        spacing=15.0,
        sizing=Sizing(width=295.0, height=48.0),
        children=[
            _icon_only_social_row("56:2103", left=0.0),
            _icon_only_social_row("56:2104", left=77.5),
            _icon_only_social_row("56:2105", left=155.0),
            _icon_only_social_row("56:2106", left=232.5),
        ],
    )
    body = render_node_body(host, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Stack(fit: StackFit.passthrough, children: [Expanded" not in compact
    assert "SizedBox(width: double.infinity, height: 48.0" not in compact
    assert "SizedBox(, height:" not in compact
    assert compact.count("Expanded(child:") >= 4
    _assert_inkwell_hosts_no_flex_parent_data(compact)


def test_login_version_10_full_emit_social_row_has_valid_flex_tree() -> None:
    """Law: social_button_row_children_must_be_finite_flex_children (processed root)."""
    root = _load_processed_root()
    layout = render_layout_file(root, feature_name="login_version_10_flex", uses_svg=False)[
        "lib/generated/login_version_10_flex_layout.dart"
    ]
    compact = layout.replace("\n", "")
    assert "Stack(fit: StackFit.passthrough, children: [Expanded" not in compact
    assert "SizedBox(, height:" not in compact
    assert compact.count("InkWell(") >= 4
    _assert_inkwell_hosts_no_flex_parent_data(compact)


def test_checkbox_label_row_must_not_wrap_expanded_in_intrinsic_width() -> None:
    """Law: intrinsic_width_row_must_not_wrap_expanded_flex_child."""
    root = _load_processed_root()
    remember_row = _find_node(root, "55:2054")
    assert remember_row is not None
    body = render_node_body(remember_row, uses_svg=False)
    compact = body.replace("\n", "")
    assert "Remember me" in compact
    assert "Expanded(child: Text('Remember me'" not in compact


def test_login_version_10_card_inflow_column_has_loose_height_budget() -> None:
    """Law: card_host_height_conserves_content."""
    root = _load_processed_root()
    layout = render_layout_file(root, feature_name="login_version_10_overflow", uses_svg=False)[
        "lib/generated/login_version_10_overflow_layout.dart"
    ]
    chunk = _layout_chunk_for_node(layout, "55_2044")
    assert "OverflowBox(alignment: Alignment.topCenter, maxHeight: 513.0" in chunk


def test_ambient_blurred_vector_prefers_native_blur_emit() -> None:
    """Law: ambient_blurred_fill_covers_base."""
    node = _ambient_wallpaper_ellipse("54:2042", "Ellipse 1")
    node = node.model_copy(
        update={"style": node.style.model_copy(update={"layer_blur": 368.0})},
    )
    body = render_node_body(node, uses_svg=False)
    compact = body.replace("\n", "")
    assert "ImageFiltered(" in compact
    assert "Image.asset(" not in compact


def test_decorative_raster_blur_wraps_image_filtered() -> None:
    """Law: decorative_blur_child_must_preserve_source_blur_not_flat_white_bloom."""
    node = CleanDesignTreeNode(
        id="56:2126",
        name="Ellipse 1",
        type=NodeType.VECTOR,
        sizing=Sizing(width=320.5, height=320.5),
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=192.0, top=-170.5, width=320.5, height=320.5),
        image_asset_key="assets/images/ellipse_1_56_2126.png",
        style=NodeStyle(background_color="0xFFFFFFFF", layer_blur=130.0),
    )
    body = render_node_body(node, uses_svg=False)
    compact = body.replace("\n", "")
    assert "ImageFiltered(" in compact
    assert "Image.asset(" in compact
    assert "withOpacity(0.55)" not in compact


def test_stroked_checkbox_emits_visual_scale() -> None:
    """Law: checkbox_control_must_preserve_source_visual_size_not_native_default."""
    node = CleanDesignTreeNode(
        id="55:2055",
        name="player-stop",
        type=NodeType.STACK,
        sizing=Sizing(width=19.0, height=19.0),
        children=[
            CleanDesignTreeNode(
                id="I55:2055;3:13302",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=11.1, height=11.1),
                style=NodeStyle(
                    has_stroke=True,
                    border_width=1.5,
                    border_color="0xFF6C7278",
                ),
            ),
        ],
    )
    from figma_flutter_agent.generator.layout.form import render_checkbox

    body = render_checkbox(node, theme_variant="material_3")
    assert "visualScale:" in body


def test_column_wallpaper_lead_has_bounded_main_axis_extent() -> None:
    """Law: column_child_stack_must_have_bounded_main_axis_extent."""
    from figma_flutter_agent.generator.layout.file_methods import (
        LayoutMethod,
        compose_decomposed_root_widget,
    )

    status = CleanDesignTreeNode(
        id="status",
        name="Native / Status Bar",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=44.0),
        children=[],
    )
    section = CleanDesignTreeNode(
        id="card",
        name="Card",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=600.0),
        children=[],
    )
    home = CleanDesignTreeNode(
        id="home",
        name="Native / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Login Version 10",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[status, section, home],
    )
    methods = [
        LayoutMethod(name="_buildNativeStatusBar", node=status),
        LayoutMethod(name="_buildCardSection", node=section),
        LayoutMethod(name="_buildNativeHomeIndicator", node=home),
    ]
    layout = compose_decomposed_root_widget(
        screen,
        methods,
        responsive_enabled=True,
        artboard_background_lead="_buildBackground(context)",
    )
    compact = layout.replace("\n", "").replace(" ", "")
    assert "SizedBox(width:double.infinity,height:812.0,child:_buildBackground(context))" in compact
    assert (
        "SizedBox(height:44.0,child:Align(alignment:Alignment.topCenter,child:_buildNativeStatusBar(context))"
        in compact
    )


def test_sectionized_column_root_wraps_viewport_chrome_and_viewport() -> None:
    """Law: column_child_stack_must_have_bounded_main_axis_extent + responsive_column_root viewport."""
    import json
    from pathlib import Path

    from figma_flutter_agent.generator.ir.passes.sectionize import (
        _apply_sectionize_clean,
        evaluate_root_sectionize,
    )
    from figma_flutter_agent.generator.layout import render_layout_file
    from figma_flutter_agent.schemas import CleanDesignTreeNode

    path = Path(".debug/screen/limbo/login_version_10/processed.json")
    if not path.is_file():
        pytest.skip("login_version_10 debug dumps not available")
    processed = json.loads(path.read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    plan = evaluate_root_sectionize(root, responsive_reflow_enabled=True)
    assert plan.activated
    sectionized = _apply_sectionize_clean(root, plan)
    layout = render_layout_file(
        sectionized,
        feature_name="login_sectionized_column",
        uses_svg=False,
        responsive_enabled=True,
    )["lib/generated/login_sectionized_column_layout.dart"]
    compact = layout.replace("\n", "").replace(" ", "")
    assert "SizedBox(height:44.0,child:Align(alignment:Alignment.topCenter" in compact
    assert "_artboardPreviewWidth" in layout
    assert "LayoutBuilder" in layout


def test_responsive_column_root_keeps_artboard_viewport_for_standard_phone() -> None:
    """Law: responsive_column_root_must_not_drop_artboard_bounds."""
    from figma_flutter_agent.generator.layout.file_methods import (
        LayoutMethod,
        compose_decomposed_root_widget,
    )

    body = CleanDesignTreeNode(
        id="body",
        name="Body",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=700.0),
        children=[],
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=812.0, height_mode=SizingMode.FIXED),
        children=[body],
    )
    methods = [LayoutMethod(name="_buildBody", node=body)]
    layout = compose_decomposed_root_widget(
        screen,
        methods,
        responsive_enabled=True,
    )
    assert (
        "LayoutBuilder" in layout
        or "SizedBox(width: 375.0, height: 812.0" in layout
        or "constraints.maxWidth" in layout
        or ("SizedBox(height: 700.0" in layout and "_buildBody(context)" in layout)
    )
