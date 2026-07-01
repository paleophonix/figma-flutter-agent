"""Regression laws for inline labeled input hosts (sign_up_version_9 family)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.flex_policy.stack import stack_should_flow_as_column
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.interaction.inline_input_hosts import (
    layout_fact_inline_labeled_input_field_host,
    layout_fact_phone_composite_field_host,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Padding, Sizing

_SIGN_UP_V9_DEBUG = Path(".debug/screen/limbo/sign_up_version_9")


def _load_processed() -> dict:
    path = _SIGN_UP_V9_DEBUG / "processed.json"
    if not path.is_file():
        pytest.skip("sign_up_version_9 debug dumps not available")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_root() -> CleanDesignTreeNode:
    return CleanDesignTreeNode.model_validate(_load_processed()["cleanTree"])


def _inline_input_field_column(
    node_id: str,
    *,
    label: str,
    value: str,
    trailing_vector: CleanDesignTreeNode | None = None,
) -> CleanDesignTreeNode:
    value_row_children: list[CleanDesignTreeNode] = [
        CleanDesignTreeNode(
            id=f"{node_id}:value-wrap",
            name="Frame",
            type=NodeType.ROW,
            sizing=Sizing(width=200.0, height=21.0),
            children=[
                CleanDesignTreeNode(
                    id=f"{node_id}:value",
                    name=value,
                    type=NodeType.TEXT,
                    text=value,
                    sizing=Sizing(width=200.0, height=21.0),
                    style=NodeStyle(font_size=14.0, text_color="0xFF1A1C1E"),
                ),
            ],
        ),
    ]
    if trailing_vector is not None:
        value_row_children.append(trailing_vector)
    return CleanDesignTreeNode(
        id=node_id,
        name="Input Field",
        type=NodeType.COLUMN,
        spacing=2.0,
        sizing=Sizing(width=279.0, height=69.0),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:label",
                name="Title",
                type=NodeType.ROW,
                sizing=Sizing(width=59.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id=f"{node_id}:label-text",
                        name=label,
                        type=NodeType.TEXT,
                        text=label,
                        sizing=Sizing(width=59.0, height=19.0),
                        style=NodeStyle(font_size=12.0, text_color="0xFF6C7278"),
                    ),
                ],
            ),
            CleanDesignTreeNode(
                id=f"{node_id}:surface",
                name="Input Area",
                type=NodeType.ROW,
                padding=Padding(top=27.0, bottom=27.0, left=14.0, right=14.0),
                sizing=Sizing(width=279.0, height=46.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_color="0xFFEDF1F3",
                    border_radius=10.0,
                    border_width=1.0,
                ),
                children=value_row_children,
            ),
        ],
    )


def test_inline_labeled_input_field_host_fact_matches_component_column() -> None:
    field = _inline_input_field_column("email", label="Email", value="Loisbecket@gmail.com")
    assert layout_fact_inline_labeled_input_field_host(field)


def test_inlined_input_host_emits_text_form_field_not_static_value() -> None:
    """Law: inlined_input_host_must_emit_functional_textfield_with_bounded_padding."""
    field = _inline_input_field_column("email", label="Email", value="Loisbecket@gmail.com")
    body = render_node_body(field, uses_svg=True, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "TextFormField" in compact
    assert "Text('Loisbecket@gmail.com'" not in compact
    assert "padding: const EdgeInsets.fromLTRB(14.0, 27.0, 14.0, 27.0)" not in compact
    assert "height: 46.0" in compact


def test_inline_input_host_binds_trailing_suffix_icon() -> None:
    trailing = CleanDesignTreeNode(
        id="eye",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=16.0, height=16.0),
        vector_asset_key="assets/icons/eye.svg",
        style=NodeStyle(has_stroke=True),
    )
    field = _inline_input_field_column(
        "password",
        label="Set Password",
        value="*******",
        trailing_vector=trailing,
    )
    body = render_node_body(field, uses_svg=True, parent_type=NodeType.COLUMN)
    assert "suffixIcon:" in body


def test_auth_stack_with_centered_logo_preserves_stack_layout() -> None:
    """Law: auth_absolute_stack_children_must_not_decompose_to_flow_column."""
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    assert stack_should_flow_as_column(root) is False


def test_sign_up_layout_emits_text_form_fields_and_positioned_logo() -> None:
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_laws", uses_svg=True)[
        "lib/generated/sign_up_version_9_laws_layout.dart"
    ]
    assert layout.count("TextFormField") >= 4
    assert "ellipse_1" in layout
    assert "Positioned(" in layout
    assert "centerLeft" not in layout.split("_buildLogo")[1].split("_buildContent")[0]


def test_phone_composite_field_host_fact_matches_country_prefix_column() -> None:
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    phone_form = None

    def find_phone_form(node: CleanDesignTreeNode) -> None:
        nonlocal phone_form
        if node.name == "Phone Form":
            phone_form = node
            return
        for child in node.children:
            find_phone_form(child)

    find_phone_form(root)
    assert phone_form is not None
    assert layout_fact_phone_composite_field_host(phone_form)


def test_sign_up_pipeline_emit_preserves_back_nav_after_sectionize() -> None:
    """Law: generate_emit_must_match_regression_render_path."""
    from figma_flutter_agent.generator.ir.passes.planner import apply_layout_passes_for_layout_emit
    from figma_flutter_agent.generator.normalize import (
        clear_extracted_refs_for_inline_hosts,
        normalize_clean_tree,
        replan_geometry_after_layout_passes,
    )
    from figma_flutter_agent.schemas import ScreenIr

    base = _SIGN_UP_V9_DEBUG
    if not (base / "processed.json").is_file() or not (base / "pre_emit.json").is_file():
        pytest.skip("sign_up_version_9 debug dumps not available")
    processed = _load_processed()
    pre = json.loads((base / "pre_emit.json").read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    screen_ir = ScreenIr.model_validate(pre["screenIr"])
    tree = normalize_clean_tree(
        root,
        screen_ir=screen_ir,
        use_geometry_planner=True,
        apply_render_safety=True,
    )
    tree = apply_layout_passes_for_layout_emit(tree, screen_ir=screen_ir)
    tree = replan_geometry_after_layout_passes(tree, project_dir=None)
    tree = clear_extracted_refs_for_inline_hosts(tree)
    layout = render_layout_file(
        tree,
        feature_name="sign_up_version_9_pipeline",
        uses_svg=True,
        skip_layout_reconcile=True,
        screen_ir=screen_ir,
    )["lib/generated/sign_up_version_9_pipeline_layout.dart"]
    assert "back-nav" in layout
    assert "InkWell(" in layout
    assert "vector_I49_1740;4_70829.svg', width: 14.0, height: 8.0" in layout
    assert "SizedBox(width: 24.0, height: 24.0, child: SvgPicture" not in layout


def test_sign_up_layout_emits_tappable_back_nav_and_bounded_phone_prefix() -> None:
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_nav_prefix", uses_svg=True)[
        "lib/generated/sign_up_version_9_nav_prefix_layout.dart"
    ]
    assert "back-nav" in layout
    assert "InkWell(" in layout
    assert "vector_I49_1740;4_70829.svg', width: 14.0, height: 8.0" in layout
    assert "fromLTRB(14.0, 27.0" not in layout
    assert "fromLTRB(14.0, 23.5" not in layout
    prefix = layout.split("prefix-dropdown")[1][:1200]
    assert "BorderRadius.horizontal(left: Radius.circular(10.0))" in prefix
    assert "height: 46.0" in prefix
    assert "MainAxisAlignment.start" in prefix
    assert "Center(child: Row(mainAxisSize: MainAxisSize.min" not in prefix


def test_sign_up_heading_is_not_wrapped_as_button_surface() -> None:
    """Law: control_surface_must_be_clickable_not_only_visual — static headings stay non-tappable."""
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_heading_tap", uses_svg=True)[
        "lib/generated/sign_up_version_9_heading_tap_layout.dart"
    ]
    sign_up_index = layout.index("Text('Sign Up'")
    assert sign_up_index >= 0
    heading_chunk = layout[max(0, sign_up_index - 400) : sign_up_index + 80]
    assert "InkWell(" not in heading_chunk
    assert "GestureDetector(" not in heading_chunk


def test_sign_up_heading_emits_gradient_shader_not_theme_primary() -> None:
    """Law: text_fill_must_emit_source_gradient_or_color_not_theme_primary_fallback."""
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_heading", uses_svg=True)[
        "lib/generated/sign_up_version_9_heading_layout.dart"
    ]
    sign_up_index = layout.index("Text('Sign Up'")
    assert sign_up_index >= 0
    heading = layout[max(0, sign_up_index - 320) : sign_up_index + 320]
    assert "LinearGradient(" in heading
    assert "createShader(bounds)" in heading
    assert "0xFF4983F6" in heading
    assert "Colors.white" in heading
    assert "AppColors.primary" not in heading


def test_sign_up_primary_cta_inkwell_covers_full_row_surface() -> None:
    """Law: primary_cta_surface_must_be_the_click_target_not_only_label."""
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_9_cta", uses_svg=True)[
        "lib/generated/sign_up_version_9_cta_layout.dart"
    ]
    assert "custom-code" in layout
    register_idx = layout.index("Text('Register'")
    assert register_idx >= 0
    register_chunk = layout[max(0, register_idx - 1400) : register_idx + 200]
    assert "InkWell(" in register_chunk
    assert "figma-49_1685:button-action" in register_chunk
    label_prefix = layout[max(0, register_idx - 500) : register_idx]
    assert "GestureDetector(" not in label_prefix
    assert "3_6045:button-action" not in label_prefix
    assert "onTap: () {}" not in layout.split("Register")[1][:400]


def test_sign_up_ambient_background_shares_artboard_stack_with_content() -> None:
    """Law: background_layers_must_share_the_same_artboard_stack_as_content."""
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(
        root,
        feature_name="sign_up_version_9_artboard_bg",
        uses_svg=True,
        responsive_enabled=False,
    )["lib/generated/sign_up_version_9_artboard_bg_layout.dart"]
    assert "_buildBackground(context)" in layout
    preview_branch = layout.split("if (_artboardPreviewWidth > 0")[1]
    assert "_buildBackground(context)" in preview_branch
    host_prefix = layout.split("LayoutBuilder(")[0]
    assert "Positioned.fill(" not in host_prefix


def test_sign_up_ambient_wallpaper_bleed_left_preserved() -> None:
    """Law: ambient_wallpaper_bleed_must_bypass_artboard_placement_clamps."""
    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    from figma_flutter_agent.generator.normalize import reconcile_layout_tree

    reconciled = reconcile_layout_tree(root)
    from figma_flutter_agent.generator.background import collect_ambient_background_children

    ambient = collect_ambient_background_children(reconciled)
    assert ambient
    ellipse = next(child for child in ambient if "ellipse" in (child.name or "").lower())
    assert ellipse.stack_placement is not None
    assert float(ellipse.stack_placement.left) < -200.0
    layout = render_layout_file(
        reconciled,
        feature_name="sign_up_version_9_bleed",
        uses_svg=True,
        skip_layout_reconcile=True,
    )["lib/generated/sign_up_version_9_bleed_layout.dart"]
    assert "left: -233" in layout or "left: -233.0" in layout


def test_sign_up_static_responsiveness_report_uses_preview_branch() -> None:
    """Law: responsiveness_report_must_reflect_runtime_preview_branch."""
    from figma_flutter_agent.generator.checks.layout import build_responsiveness_report

    processed = _load_processed()
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    report = build_responsiveness_report(root, responsive_enabled=False)
    assert report["active_branch_interactive_dev"] == "preview_interactive"
    assert report["active_branch_golden_capture"] == "preview_capture"
