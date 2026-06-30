"""Regression laws for mixed inflow stack overlays (sign_up_version_5 family)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.background import (
    extract_nested_decorative_backgrounds,
    partition_wallpaper_foreground_tree,
)
from figma_flutter_agent.generator.background.detection import (
    is_decorative_absolute_background_overlay,
)
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.normalize import reconcile_layout_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode


def _load_root() -> CleanDesignTreeNode:
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_5/processed.json").read_text(encoding="utf-8")
    )
    return CleanDesignTreeNode.model_validate(processed["cleanTree"])


def test_sign_up_version_5_absolute_overlay_is_direct_stack_child() -> None:
    """Law: positioned_widget_must_be_direct_child_of_stack."""
    root = _load_root()
    layout = render_layout_file(root, feature_name="sign_up_version_5_overlay", uses_svg=True)[
        "lib/generated/sign_up_version_5_overlay_layout.dart"
    ]
    compact = layout.replace("\n", "")
    assert "figma-42_2283" in compact or "_buildBackground" in compact
    assert "SizedBox(width: double.infinity, child: Positioned(" not in compact


def test_sign_up_version_5_interleaved_absolute_emits_single_flow_column() -> None:
    """Law: stack_flow_children_coalesced_into_single_column."""
    root = _load_root()
    layout = render_layout_file(root, feature_name="sign_up_version_5_flow_column", uses_svg=True)[
        "lib/generated/sign_up_version_5_flow_column_layout.dart"
    ]
    compact = layout.replace("\n", "")
    content_idx = compact.find("figma-42_2282")
    assert content_idx >= 0
    content_chunk = compact[content_idx : content_idx + 20000]
    assert "Get Started now" in content_chunk
    assert "First Name" in content_chunk
    assert (
        content_chunk.count(
            "Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, spacing: 24.0"
        )
        >= 1
        or "spacing: 24.0" in content_chunk
    )


def test_sign_up_version_5_pattern_is_decorative_background_overlay() -> None:
    """Law: render_boundary_flattened_pattern_is_decorative_background_overlay."""
    root = _load_root()
    pattern = next(
        child
        for child in root.children[0].children
        if child.name == "Pattern"
    )
    assert is_decorative_absolute_background_overlay(pattern)


def test_sign_up_version_5_nested_pattern_hoisted_to_artboard_background() -> None:
    """Law: decorative_background_layers_must_paint_behind_content_inside_artboard_stack."""
    root = reconcile_layout_tree(_load_root())
    pruned, extracted = extract_nested_decorative_backgrounds(root)
    assert any(node.id.endswith("2283") for node in extracted)
    assert not any(
        child.id.endswith("2283")
        for child in pruned.children[0].children
        if pruned.children and pruned.children[0].id.endswith("2282")
    )
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_artboard_bg",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_artboard_bg_layout.dart"]
    assert "_buildBackground(context)" in layout


def test_sign_up_version_5_pattern_paints_behind_flow_column() -> None:
    """Law: decorative_absolute_overlay_must_paint_behind_inflow_siblings."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_paint_order",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_paint_order_layout.dart"]
    compact = layout.replace("\n", "")
    bg_idx = compact.find("_buildBackground(context)")
    content_idx = compact.find("_buildContent(context)")
    assert bg_idx >= 0 and content_idx >= 0
    assert bg_idx < content_idx


def test_sign_up_version_5_pattern_uses_artboard_hoisted_placement() -> None:
    """Law: hoisted_nested_decorative_must_emit_artboard_world_coordinates."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_placement",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_placement_layout.dart"]
    assert "top: 224.5" not in layout
    assert "top: 30.0" in layout or "top: 30," in layout


def test_sign_up_version_5_flow_gap_preserves_autolayout_spacing() -> None:
    """Law: autolayout_item_spacing_preserved."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_flow_gap",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_flow_gap_layout.dart"]
    compact = layout.replace("\n", "")
    content_idx = compact.find("figma-42_2282")
    assert content_idx >= 0
    chunk = compact[content_idx : content_idx + 12000]
    assert "SizedBox(height: 114" not in chunk
    assert "SizedBox(height: 24.0)" in chunk or "SizedBox(height: 24)," in chunk


def test_sign_up_version_5_logo_centered_in_content_column() -> None:
    """Law: counter_axis_center_applies_to_all_children."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_logo_center",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_logo_center_layout.dart"]
    compact = layout.replace("\n", "")
    logo_idx = compact.find("vector_42_2337.svg")
    assert logo_idx >= 0
    prefix = compact[max(0, logo_idx - 220) : logo_idx]
    assert "Alignment.centerLeft" not in prefix
    assert "Alignment.center," in prefix or "Alignment.center)" in prefix


def test_sign_up_version_5_subtitle_preserves_fixed_text_box_width() -> None:
    """Law: fixed_text_width_preserved."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_subtitle_width",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_subtitle_width_layout.dart"]
    compact = layout.replace("\n", "")
    subtitle_idx = compact.find("Create an account or log in to explore about our app")
    assert subtitle_idx >= 0
    chunk = compact[subtitle_idx : subtitle_idx + 500]
    assert "width: 222.0" in chunk
    assert "width: double.infinity" not in chunk.split("Text('Create an account", 1)[0]


def test_sign_up_version_5_subtitle_center_aligned_in_parent() -> None:
    """Law: center_aligned_fixed_width_multiline_text_must_center_in_parent."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_subtitle_center",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_subtitle_center_layout.dart"]
    compact = layout.replace("\n", "")
    subtitle_idx = compact.find("Create an account or log in to explore about our app")
    assert subtitle_idx >= 0
    chunk = compact[max(0, subtitle_idx - 400) : subtitle_idx + 350]
    assert "Alignment.centerLeft" not in chunk
    assert "SizedBox(width: 222.0, child: Center(child:" in chunk


def test_sign_up_version_5_static_root_skips_scroll_shell() -> None:
    """Law: static_artboard_mode_must_not_use_scroll_shell_unless_source_requires_scroll."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_static",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_static_layout.dart"]
    fallback = layout.split("if (_artboardPreviewWidth > 0")[0]
    assert "SingleChildScrollView" not in fallback


def test_sign_up_version_5_phone_prefix_inherits_leading_radius_and_height() -> None:
    """Law: composite_input_prefix_must_inherit_outer_left_radius_and_fit_parent_height."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_phone_prefix",
        uses_svg=True,
    )["lib/generated/sign_up_version_5_phone_prefix_layout.dart"]
    compact = layout.replace("\n", "")
    phone_idx = compact.find("Phone Number")
    assert phone_idx >= 0
    chunk = compact[phone_idx : phone_idx + 4500]
    assert "BorderRadius.horizontal(left: Radius.circular(10.0))" in chunk
    prefix_slot = chunk.split("BorderRadius.horizontal(left: Radius.circular(10.0))", 1)[1][:2500]
    assert "height: 48.0" not in prefix_slot
    assert "height: 46.0" in prefix_slot


def test_sign_up_version_5_phone_prefix_suppresses_redundant_inner_stroke() -> None:
    """Law: composite_input_prefix_must_suppress_redundant_inner_stroke."""
    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_phone_prefix_border",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_phone_prefix_border_layout.dart"]
    compact = layout.replace("\n", "")
    phone_idx = compact.find("prefix-dropdown")
    assert phone_idx >= 0
    prefix_slot = compact[phone_idx : phone_idx + 1200]
    assert "Border.all(color: Color(0xFF000000)" not in prefix_slot
    assert "border: Border.all" not in prefix_slot


def test_sign_up_version_5_pattern_svg_uses_contain_not_fill() -> None:
    """Law: decorative_render_boundary_svg_must_not_stretch_with_boxfit_fill."""
    from figma_flutter_agent.generator.layout.widgets.svg import _svg_fit_mode

    pattern = next(
        child
        for child in _load_root().children[0].children
        if child.name == "Pattern"
    )
    assert pattern.render_boundary is True
    assert pattern.flatten_figma_node_ids
    width = float(pattern.sizing.width or 0.0)
    height = float(pattern.sizing.height or 0.0)
    assert _svg_fit_mode(pattern, width, height) == "BoxFit.contain"

    root = _load_root()
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_5_pattern_fit",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_5_pattern_fit_layout.dart"]
    bg_chunk = layout.split("figma-42_2283", 1)[-1][:400]
    assert "BoxFit.fill" not in bg_chunk or "SizedBox.shrink()" in bg_chunk


def test_sign_up_version_5_partition_collects_nested_pattern() -> None:
    """Law: decorative_background_layers_must_paint_behind_content_inside_artboard_stack."""
    root = reconcile_layout_tree(_load_root())
    _, wallpaper_children, _ = partition_wallpaper_foreground_tree(root)
    assert any(child.id.endswith("2283") for child in wallpaper_children)
