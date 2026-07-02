"""Regression tests for chip stack, nav header, checkbox, and stroke emit laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout.flex_policy import stack_should_flow_as_column
from figma_flutter_agent.generator.layout.flex_policy.row import (
    layout_fact_stack_tab_switcher_host,
)
from figma_flutter_agent.generator.layout.navigation.items import (
    layout_fact_stack_bottom_nav_tab_glyph_column,
)
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.emit.shell import prepare_layout_children
from figma_flutter_agent.generator.layout.widgets.position import _render_leaf_surface
from figma_flutter_agent.generator.layout.widgets.svg import (
    stack_should_emit_flattened_vector_group,
)
from figma_flutter_agent.parser.interaction import (
    stack_hosts_checkbox_label_pair,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.interaction.forms import (
    checkbox_option_stack_is_checked,
    layout_fact_checkbox_control,
)
from figma_flutter_agent.parser.interaction.icons import (
    layout_fact_stack_vertical_icon_label_chip_tile,
    layout_fact_upload_placeholder_tile,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)

_FOOD_DEBUG = Path(".debug/screen/limbo/food_add_new_items")


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _load_food_root() -> CleanDesignTreeNode:
    path = _FOOD_DEBUG / "processed.json"
    if not path.is_file():
        pytest.skip("food_add_new_items debug bundle unavailable")
    processed = json.loads(path.read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    from figma_flutter_agent.parser.dedup.hydrate import hydrate_pruned_cluster_instances

    hydrate_pruned_cluster_instances(root)
    return root


def _ingredient_chip_stack() -> CleanDesignTreeNode:
    """Absolute icon + plate + label chip; must not flow as bottom-nav column."""
    return CleanDesignTreeNode(
        id="1:chip",
        name="Ingredient",
        type=NodeType.STACK,
        sizing=Sizing(width=50.0, height=70.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Tomato",
                sizing=Sizing(width=36.0, height=13.0),
                stack_placement=StackPlacement(
                    horizontal="SCALE",
                    left=7.0,
                    top=57.0,
                    width=36.0,
                    height=13.0,
                ),
            ),
            CleanDesignTreeNode(
                id="1:plate",
                name="Circle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=50.0, height=50.0),
                style=NodeStyle(
                    background_color="0xFFFDFDFD",
                    border_color="0xFFE8EAED",
                    border_width=1.0,
                    stroke_align="OUTSIDE",
                    border_radius=25.0,
                ),
                stack_placement=StackPlacement(
                    horizontal="LEFT",
                    left=0.0,
                    top=0.0,
                    width=50.0,
                    height=50.0,
                ),
            ),
            CleanDesignTreeNode(
                id="1:icon",
                name="Icon",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
                stack_placement=StackPlacement(
                    horizontal="LEFT",
                    left=13.0,
                    top=13.0,
                    width=24.0,
                    height=24.0,
                ),
            ),
        ],
    )


def _app_bar_header_stack() -> CleanDesignTreeNode:
    """Three-slot nav header: trailing action, back, centered title."""
    return CleanDesignTreeNode(
        id="1:header",
        name="Header",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=45.0),
        children=[
            CleanDesignTreeNode(
                id="1:reset",
                name="Reset",
                type=NodeType.TEXT,
                text="Reset",
                sizing=Sizing(width=40.0, height=17.0),
            ),
            CleanDesignTreeNode(
                id="1:back",
                name="Back",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Add New Items",
                sizing=Sizing(width=120.0, height=22.0),
            ),
        ],
    )


def _checkbox_option_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:option",
        name="Delivery option",
        type=NodeType.STACK,
        sizing=Sizing(width=120.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:box",
                name="Checkbox",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=20.0, height=20.0),
                style=NodeStyle(border_color="0xFFE8EAED", border_width=1.0),
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Delivery",
                sizing=Sizing(width=60.0, height=17.0),
            ),
        ],
    )


def test_absolute_chip_stack_not_bottom_nav_glyph_column() -> None:
    """Law: positioned_child_requires_stack_parent — no column lowering for overlay chips."""
    chip = _ingredient_chip_stack()
    assert not layout_fact_stack_bottom_nav_tab_glyph_column(chip)
    assert not stack_should_flow_as_column(chip)


def test_app_bar_header_not_tab_switcher_host() -> None:
    """Law: app_bar_slots_leading_center_title_trailing_action."""
    header = _app_bar_header_stack()
    assert not layout_fact_stack_tab_switcher_host(header)


def test_stack_checkbox_label_pair_detected() -> None:
    """Law: compound_input_may_contain_option_controls_without_retyping_options_as_text_fields."""
    stack = _checkbox_option_stack()
    assert stack_hosts_checkbox_label_pair(stack)


def test_stack_checkbox_emits_row_not_text_field() -> None:
    """Checkbox option stacks must not compile as TextField hosts."""
    emitted = render_node_body(
        _checkbox_option_stack(),
        uses_svg=True,
        parent_type=NodeType.COLUMN,
    )
    compact = emitted.replace("\n", "")
    assert "Checkbox" in compact or "checkbox" in compact.lower()
    assert "TextField(" not in compact
    assert "TextFormField(" not in compact


def test_outside_stroke_leaf_surface_emits_foreground_decoration() -> None:
    """Law: container_stroke_preserved — OUTSIDE strokes use foregroundDecoration."""
    plate = CleanDesignTreeNode(
        id="1:plate",
        name="Circle",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=50.0, height=50.0),
        style=NodeStyle(
            background_color="0xFFFDFDFD",
            border_color="0xFFE8EAED",
            border_width=1.0,
            stroke_align="OUTSIDE",
            border_radius=25.0,
        ),
    )
    emitted = _render_leaf_surface(plate)
    assert emitted is not None
    assert "foregroundDecoration" in emitted
    assert "0xFFE8EAED" in emitted


def test_upload_strip_overflow_wraps_horizontal_scroll() -> None:
    """Law: overflowing_horizontal_content_strip_must_scroll."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_stack_overflowing_horizontal_content_strip,
    )

    parent = CleanDesignTreeNode(
        id="1:parent",
        name="Body",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=200.0),
    )
    strip = CleanDesignTreeNode(
        id="1:strip",
        name="Upload strip",
        type=NodeType.STACK,
        sizing=Sizing(width=381.0, height=111.0),
        children=[
            CleanDesignTreeNode(
                id="1:a",
                name="Tile",
                type=NodeType.STACK,
                sizing=Sizing(width=111.0, height=111.0),
            ),
            CleanDesignTreeNode(
                id="1:b",
                name="Tile",
                type=NodeType.STACK,
                sizing=Sizing(width=111.0, height=111.0),
            ),
        ],
    )
    assert layout_fact_stack_overflowing_horizontal_content_strip(
        strip,
        parent_node=parent,
    )
    emitted = render_node_body(
        strip,
        uses_svg=True,
        parent_type=NodeType.STACK,
        parent_node=parent,
    )
    assert "SingleChildScrollView(scrollDirection: Axis.horizontal" in emitted.replace("\n", "")


def test_single_line_input_vertical_center_uses_center_align() -> None:
    """Law: single_line_input_vertical_center."""
    from figma_flutter_agent.generator.layout.widgets.input.fields import (
        _prefilled_input_field_expr,
    )

    field = _prefilled_input_field_expr(
        escaped_value="Item",
        obscure="false",
        input_style="Theme.of(context).textTheme.bodyMedium",
        decoration="const InputDecoration(border: InputBorder.none)",
        vertical_center=True,
    )
    assert "TextAlignVertical.center" in field
    assert "TextAlignVertical.top" not in field


def test_ingredient_chip_stack_not_classified_as_input() -> None:
    """Law: vertical_icon_label_chip_not_form_field."""
    chip = _ingredient_chip_stack()
    assert layout_fact_stack_vertical_icon_label_chip_tile(chip)
    assert stack_interaction_kind(chip) == "button"
    emitted = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "TextField(" not in compact
    assert "keyboard_arrow_down" not in compact


def test_food_replay_ingredient_chips_not_text_fields() -> None:
    """Replay corpus chips must not compile as dropdown text fields."""
    root = _load_food_root()
    for node_id in ("602:1142", "602:1169", "602:1153", "602:1098"):
        chip = _find_node(root, node_id)
        assert chip is not None, node_id
        assert stack_interaction_kind(chip) == "button", node_id
        emitted = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
        compact = emitted.replace("\n", "")
        assert "TextField(" not in compact, node_id
        assert "keyboard_arrow_down" not in compact, node_id


def test_stack_emit_zip_survives_omitted_children() -> None:
    """Law: StackEmitChildWidgetZipAlignmentLaw — zip only emitted (child, widget) pairs."""
    root = _load_food_root()
    tile = _find_node(root, "602:1184")
    assert tile is not None
    (
        sorted_children,
        _metadata_column_host,
        paired_circle_ids,
        omit_child_ids,
        playback_seek_ids,
        playback_decor_omit_ids,
        _merged_thumb_widgets,
    ) = prepare_layout_children(tile, is_layout_root=False, parent_node=None)
    skip_ids = paired_circle_ids | omit_child_ids | playback_seek_ids | playback_decor_omit_ids
    emitted_count = sum(1 for child in sorted_children if child.id not in skip_ids)
    assert len(sorted_children) > emitted_count
    render_node_body(tile, uses_svg=True, parent_type=NodeType.STACK)


def test_food_replay_upload_tile_not_text_field() -> None:
    """Law: upload_placeholder_not_text_field."""
    root = _load_food_root()
    tile = _find_node(root, "602:1184")
    assert tile is not None
    assert layout_fact_upload_placeholder_tile(tile)
    assert stack_interaction_kind(tile) == "button"
    emitted = render_node_body(tile, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "TextField(" not in compact


def test_compact_icon_glyph_group_not_flattened() -> None:
    """Law: icon_chip_glyph_children_not_parent_flatten."""
    group = CleanDesignTreeNode(
        id="1:glyph",
        name="Icon group",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        vector_svg_path_count=3,
        children=[
            CleanDesignTreeNode(
                id="1:v1",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=10.0, height=10.0),
            ),
            CleanDesignTreeNode(
                id="1:v2",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=12.0, height=8.0),
            ),
        ],
    )
    assert not stack_should_emit_flattened_vector_group(group)


def test_checkbox_checked_from_inline_checkmark_vector() -> None:
    """Law: checkbox_reflects_figma_state_and_style."""
    stack = CleanDesignTreeNode(
        id="1:option",
        name="Pick up",
        type=NodeType.STACK,
        sizing=Sizing(width=75.0, height=19.0),
        children=[
            CleanDesignTreeNode(
                id="1:box",
                name="Rectangle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=18.0, height=18.0),
                style=NodeStyle(
                    border_color="0xFFFB6D3A",
                    border_width=1.0,
                    border_radius=3.0,
                    has_stroke=True,
                ),
                stack_placement=StackPlacement(top=1.0, right=57.0, width=18.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Pick up",
                type=NodeType.TEXT,
                text="Pick up",
                sizing=Sizing(width=47.0, height=16.0),
                stack_placement=StackPlacement(left=28.0, bottom=3.0, width=47.0, height=16.0),
            ),
            CleanDesignTreeNode(
                id="1:mark",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=8.0, height=6.0),
                style=NodeStyle(border_color="0xFFFB6D3A", border_width=1.5, has_stroke=True),
                stack_placement=StackPlacement(left=5.0, top=7.0, width=8.0, height=6.0),
            ),
        ],
    )
    assert stack_hosts_checkbox_label_pair(stack)
    assert checkbox_option_stack_is_checked(stack)
    emitted = render_node_body(stack, uses_svg=True, parent_type=NodeType.COLUMN)
    compact = emitted.replace("\n", "")
    assert "initialValue: true" in compact
    assert "checkboxTheme: CheckboxThemeData" in compact
    assert "0xFFFB6D3A" in compact
    assert "spacing:" in compact


def test_food_replay_pick_up_checkbox_checked_and_spaced() -> None:
    root = _load_food_root()
    stack = _find_node(root, "602:1210")
    assert stack is not None
    assert checkbox_option_stack_is_checked(stack)
    emitted = render_node_body(stack, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "initialValue: true" in compact
    assert "TextField(" not in compact
    assert "0xFFFB6D3A" in compact


def test_catalog_chip_label_uses_scale_down_not_ellipsis() -> None:
    chip = _ingredient_chip_stack()
    emitted = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
    assert "FittedBox(fit: BoxFit.scaleDown" in emitted.replace("\n", "")
    assert "TextOverflow.ellipsis" not in emitted


def test_multi_vector_glyph_group_not_input_rating() -> None:
    """Law: MultiVectorIsNotRatingLaw — upload glyph groups are not star ratings."""
    from figma_flutter_agent.parser.semantics.detectors.inputs import (
        _count_rating_star_units,
        _is_rating_star_unit,
    )

    root = _load_food_root()
    glyph_group = _find_node(root, "602:1188")
    assert glyph_group is not None
    assert not _is_rating_star_unit(glyph_group)
    assert _count_rating_star_units(glyph_group) < 3


def test_inline_widget_render_blocks_sibling_cluster_delegate() -> None:
    """Law: ClusterReferenceClosureBeforePruneLaw — inline hosts do not call cluster widgets."""
    from figma_flutter_agent.generator.cluster_variants import (
        cluster_classes_for_inline_widget_render,
    )
    from figma_flutter_agent.generator.subtree.render import _prepare_subtree_render_root

    root = _load_food_root()
    badge = _find_node(root, "602:1186")
    assert badge is not None
    prepared = _prepare_subtree_render_root(badge)
    emitted = render_node_body(
        prepared,
        uses_svg=True,
        cluster_classes=cluster_classes_for_inline_widget_render(
            "UploadPhotoVideoWidget",
            {"cluster_0": "Group8228Widget"},
        ),
    )
    compact = emitted.replace("\n", "")
    assert "Group8228Widget" not in compact
    assert "SvgPicture" in compact
    assert "SizedBox.shrink" not in compact


def test_repair_stale_ctor_does_not_shrink_substantive_upload_glyph() -> None:
    """Law: PlannedWidgetGraphClosureLaw — missing ctor must not be masked as shrink."""
    from figma_flutter_agent.generator.planned.reconcile.delegate_repair import (
        repair_stale_widget_ctor_names_in_planned,
    )

    planned = {
        "lib/widgets/upload_photo_video_widget.dart": """
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
class UploadPhotoVideoWidget extends StatelessWidget {
  const UploadPhotoVideoWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      Positioned(child: Group8228Widget()),
      Positioned(child: SvgPicture.asset('assets/icons/foo.svg')),
    ]);
  }
}
""",
    }
    updated = repair_stale_widget_ctor_names_in_planned(planned)
    body = updated["lib/widgets/upload_photo_video_widget.dart"]
    assert "Group8228Widget()" in body
    assert "SizedBox.shrink" not in body


def test_painted_surface_overlay_button_emits_centered_stack() -> None:
    """Law: PaintedButtonOverlayLaw — full-cover surface centers overlaid label."""
    from figma_flutter_agent.parser.interaction.buttons import (
        button_has_icon_label_inline_affordance,
        button_has_painted_surface_overlay_label,
    )

    button = CleanDesignTreeNode(
        id="1:cta",
        name="Save",
        type=NodeType.BUTTON,
        sizing=Sizing(width=327.0, height=62.0),
        children=[
            CleanDesignTreeNode(
                id="1:bg",
                name="Background",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/cta_bg.svg",
                sizing=Sizing(width=327.0, height=62.0),
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Save Changes",
                sizing=Sizing(width=120.0, height=22.0),
            ),
        ],
    )
    assert button_has_painted_surface_overlay_label(button)
    assert not button_has_icon_label_inline_affordance(button)
    emitted = render_node_body(button, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "Stack(fit: StackFit.expand" in compact
    assert "Center(child:" in compact
    assert "Row(mainAxisAlignment: MainAxisAlignment.start" not in compact


def test_geometric_flex_order_text_before_trailing_icon() -> None:
    """Law: GeometricFlexOrderLaw — row children follow painted X order."""
    metric = CleanDesignTreeNode(
        id="see_all",
        name="See All",
        type=NodeType.STACK,
        sizing=Sizing(width=58.0, height=17.0),
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Label",
                type=NodeType.TEXT,
                text="See All",
                sizing=Sizing(width=44.0, height=17.0),
                stack_placement=StackPlacement(left=0.0, width=44.0, height=17.0),
            ),
            CleanDesignTreeNode(
                id="icon",
                name="Chevron",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/chevron.svg",
                sizing=Sizing(width=6.0, height=3.0),
                stack_placement=StackPlacement(left=52.0, width=6.0, height=3.0),
            ),
        ],
    )
    emitted = render_node_body(metric, uses_svg=True)
    compact = emitted.replace("\n", "")
    assert compact.index("See All") < compact.index("chevron.svg")


def test_labeled_absolute_field_stack_emits_external_label() -> None:
    """Law: LabeledFieldCompositeLaw — label above painted field shell."""
    from figma_flutter_agent.parser.interaction.absolute_fields import (
        layout_fact_labeled_absolute_field_stack,
    )

    field_stack = CleanDesignTreeNode(
        id="1:field",
        name="Item name",
        type=NodeType.STACK,
        sizing=Sizing(width=327.0, height=74.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="item name",
                sizing=Sizing(width=80.0, height=16.0),
                stack_placement=StackPlacement(left=24.0, top=0.0, width=80.0, height=16.0),
                geometry_frame={
                    "layoutRect": {"x": 24.0, "y": 0.0, "width": 80.0, "height": 16.0},
                },
            ),
            CleanDesignTreeNode(
                id="1:shell",
                name="Shell",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=327.0, height=50.0),
                style=NodeStyle(
                    background_color="0xFFFDFDFD",
                    border_color="0xFFE8EAED",
                    border_width=1.0,
                ),
                stack_placement=StackPlacement(left=0.0, top=24.0, width=327.0, height=50.0),
                geometry_frame={
                    "layoutRect": {"x": 0.0, "y": 24.0, "width": 327.0, "height": 50.0},
                },
            ),
            CleanDesignTreeNode(
                id="1:value",
                name="Value",
                type=NodeType.TEXT,
                text="Mazalichiken Halim",
                sizing=Sizing(width=200.0, height=20.0),
                stack_placement=StackPlacement(left=36.0, top=42.0, width=200.0, height=20.0),
                geometry_frame={
                    "layoutRect": {"x": 36.0, "y": 42.0, "width": 200.0, "height": 20.0},
                },
            ),
        ],
    )
    assert layout_fact_labeled_absolute_field_stack(field_stack)
    emitted = render_node_body(field_stack, uses_svg=True, parent_type=NodeType.COLUMN)
    compact = emitted.replace("\n", "")
    assert "Text('item name'" in compact
    assert compact.index("item name") < compact.index("Mazalichiken Halim")
    assert "Column(" in compact


def test_checkbox_theme_uses_border_color_not_surface_fill() -> None:
    """Law: CheckboxVisualContractLaw — checkbox chrome follows stroke color."""
    stack = CleanDesignTreeNode(
        id="1:option",
        name="Delivery",
        type=NodeType.STACK,
        sizing=Sizing(width=81.0, height=19.0),
        children=[
            CleanDesignTreeNode(
                id="1:box",
                name="Rectangle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=18.0, height=18.0),
                style=NodeStyle(
                    background_color="0xFFFDFDFD",
                    border_color="0xFFE8EAED",
                    border_width=1.0,
                    border_radius=3.0,
                    has_stroke=True,
                ),
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Delivery",
                type=NodeType.TEXT,
                text="Delivery",
                sizing=Sizing(width=53.0, height=16.0),
            ),
        ],
    )
    emitted = render_node_body(stack, uses_svg=True, parent_type=NodeType.COLUMN)
    compact = emitted.replace("\n", "")
    assert "side: BorderSide(color: Color(0xFFE8EAED)" in compact
    assert "Color(0xFFFDFDFD)" not in compact.split("checkboxTheme")[1].split("child:")[0]


def test_food_replay_pruned_upload_tile_rehydrates_glyph() -> None:
    """Law: PrunedClusterRepresentativeReuseLaw — duplicate upload badge keeps glyph body."""
    root = _load_food_root()
    tile = _find_node(root, "602:1194")
    assert tile is not None
    emitted = render_node_body(tile, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "group_8227" in compact
    assert "SizedBox.shrink()" not in compact


def test_food_replay_layout_file_orchestration_contracts() -> None:
    """Law: orchestration replay — full layout emit preserves repaired screen contracts."""
    from figma_flutter_agent.generator.layout import render_layout_file

    root = _load_food_root()
    files = render_layout_file(
        root,
        feature_name="food_add_new_items_laws",
        uses_svg=True,
    )
    compact = "".join(files.values()).replace("\n", "")
    assert "item name" in compact
    assert "See All" in compact
    assert compact.index("See All") < compact.rindex(".svg")
    assert "Save Changes" in compact
    assert "Stack(fit: StackFit.expand" in compact or "Center(child:" in compact
    assert "0xFFE8EAED" in compact
    assert "0xFFFB6D3A" in compact
    assert "group_8227" in compact
    assert "RenderFlex overflowed" not in compact
