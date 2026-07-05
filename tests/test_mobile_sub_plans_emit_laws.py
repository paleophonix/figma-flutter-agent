"""Regression tests for mobile_sub_plans subscription screen emit laws."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from figma_flutter_agent.generator.background import partition_wallpaper_foreground_tree
from figma_flutter_agent.generator.cluster_variants import resolve_cluster_delegate_class
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.finalize import _wrap_min_touch_target
from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs
from figma_flutter_agent.parser.interaction.inline_input_hosts import (
    flex_painted_action_surface_vetoes_input,
    layout_fact_single_surface_input_field_column,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing

_FIXTURE = Path(".debug/screen/limbo/mobile_sub_plans/processed.json")


def _load_root() -> CleanDesignTreeNode:
    if not _FIXTURE.is_file():
        pytest.skip("mobile_sub_plans debug dumps not available")
    processed = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(processed["cleanTree"])


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _cluster_classes(root: CleanDesignTreeNode) -> dict[str, str]:
    counts: Counter[str] = Counter()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            counts[node.cluster_id] += 1
        for child in node.children:
            walk(child)

    walk(root)
    summary = {cluster_id: count for cluster_id, count in counts.items() if count >= 2}
    specs = collect_cluster_widget_specs(root, summary)
    return {spec.cluster_id: spec.class_name for spec in specs}


def _render_layout(root: CleanDesignTreeNode) -> str:
    files = render_layout_file(
        root,
        feature_name="mobile_sub_plans",
        cluster_classes=_cluster_classes(root),
        uses_svg=True,
        theme_variant="material",
    )
    return "\n".join(files.values())


def test_subscribe_column_vetoes_inline_input_host() -> None:
    root = _load_root()
    action_column = _find_node(root, "267:5948")
    button_row = _find_node(root, "267:5949")
    assert action_column is not None
    assert button_row is not None
    assert flex_painted_action_surface_vetoes_input(button_row)
    assert not layout_fact_single_surface_input_field_column(action_column)


def test_subscribe_footer_does_not_emit_textformfield() -> None:
    root = _load_root()
    action_column = _find_node(root, "267:5948")
    assert action_column is not None
    dart = render_node_body(action_column, uses_svg=True, theme_variant="material")
    assert "TextFormField" not in dart
    assert "TextField" not in dart
    assert "InkWell" in dart or "onTap" in dart


def test_layout_subscribe_is_button_not_textfield() -> None:
    root = _load_root()
    layout = _render_layout(root)
    assert "initialValue: 'Subscribe'" not in layout
    assert (
        "TextFormField" not in layout
        or "Subscribe" not in layout.split("TextFormField", 1)[-1][:200]
    )


def test_star_cluster_delegates_to_star_widget_not_radio() -> None:
    root = _load_root()
    cluster_classes = _cluster_classes(root)
    star = _find_node(root, "240:6321")
    assert star is not None
    assert cluster_classes.get("component_211_5913") == "StarFilledWidget"
    assert resolve_cluster_delegate_class(star, cluster_classes) == "StarFilledWidget"
    layout = _render_layout(root)
    for label in ("Unlimited access", "200GB storage", "Sync all your devices"):
        idx = layout.find(label)
        assert idx != -1
        row = layout[max(0, idx - 320) : idx]
        assert "StarFilledWidget" in row
        assert "RadioButtonWidget" not in row


def test_selected_radio_inner_vector_stays_out_of_build_background() -> None:
    root = _load_root()
    _, wallpaper_children, _ = partition_wallpaper_foreground_tree(root)
    wallpaper_ids = {child.id for child in wallpaper_children}
    assert "I240:6294;109:2250" not in wallpaper_ids
    layout = _render_layout(root)
    assert "I240_6294_109_2250" not in layout.split("_buildBackground", 1)[-1]


def test_compact_radio_min_touch_target_does_not_expand_flex_slot() -> None:
    radio = CleanDesignTreeNode(
        id="radio:compact",
        name="Radio Button",
        type=NodeType.RADIO,
        sizing=Sizing(width=16.0, height=16.0),
        min_touch_target=44.0,
        children=[],
    )
    wrapped = _wrap_min_touch_target(radio, "const Icon(Icons.circle_outlined)")
    assert wrapped == "const Icon(Icons.circle_outlined)"
    assert "OverflowBox(" not in wrapped


def test_subscription_plan_rows_delegate_radios_not_list_tile_icons() -> None:
    root = _load_root()
    cluster_classes = _cluster_classes(root)
    layout = _render_layout(root)
    assert "const RadioButtonWidget()" in layout
    assert "Icons.circle_outlined" not in layout
    monthly_row = _find_node(root, "240:6302")
    assert monthly_row is not None
    lead = monthly_row.children[0]
    assert lead.type == NodeType.RADIO
    assert resolve_cluster_delegate_class(lead, cluster_classes) == "RadioButtonWidget"


def test_star_cluster_widget_omits_occluding_fill_plate() -> None:
    root = _load_root()
    counts: Counter[str] = Counter()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            counts[node.cluster_id] += 1
        for child in node.children:
            walk(child)

    walk(root)
    specs = collect_cluster_widget_specs(
        root, {cluster_id: count for cluster_id, count in counts.items() if count >= 2}
    )
    from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets

    result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[root])
    star_file = result.files.get("lib/widgets/star_filled_widget.dart", "")
    assert "211_5908" not in star_file
    assert "0xFF006FFD" not in star_file
    assert "Image.asset" in star_file


def test_bounded_radio_cluster_widget_uses_exact_paint_not_material_radio() -> None:
    root = _load_root()
    counts: Counter[str] = Counter()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            counts[node.cluster_id] += 1
        for child in node.children:
            walk(child)

    walk(root)
    specs = collect_cluster_widget_specs(
        root, {cluster_id: count for cluster_id, count in counts.items() if count >= 2}
    )
    from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets

    result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[root])
    radio_file = result.files.get("lib/widgets/radio_button_widget.dart", "")
    assert "Radio<String>" not in radio_file
    assert "0xFFC5C6CC" in radio_file


def test_selected_plan_radio_emits_inner_ellipse_not_material_radio() -> None:
    root = _load_root()
    radio = _find_node(root, "240:6294")
    assert radio is not None
    dart = render_node_body(radio, uses_svg=True)
    assert "Radio<String>" not in dart
    assert "ellipse_2_I240_6294" in dart
    assert "0xFF006FFD" in dart


def test_plan_rows_avoid_fixed_width_inside_expanded() -> None:
    root = _load_root()
    layout = _render_layout(root)
    assert "width: 194" not in layout
    assert "width: 196" not in layout


def test_published_star_cluster_vetoes_radio_delegate_name() -> None:
    root = _load_root()
    star = _find_node(root, "240:6321")
    assert star is not None
    cluster_classes = {
        "component_211_5913": "RadioButtonWidget",
        "component_109_2239": "RadioButtonWidget",
    }
    assert resolve_cluster_delegate_class(star, cluster_classes) is None


def test_pipeline_widget_specs_keep_star_component_family_name() -> None:
    from collections import Counter

    from figma_flutter_agent.config.settings import load_settings
    from figma_flutter_agent.generator.widget_extraction import collect_widget_specs

    root = _load_root()
    counts: Counter[str] = Counter()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            counts[node.cluster_id] += 1
        for child in node.children:
            walk(child)

    walk(root)
    settings = load_settings()
    specs = collect_widget_specs(
        root,
        dict(counts),
        config=settings.agent.generation.widget_extraction,
        widget_suffix=settings.agent.naming.widget_suffix,
        legacy_enforce=settings.agent.generation.enforce_cluster_widgets,
        legacy_min_count=settings.agent.generation.cluster_min_count,
    )
    by_cluster = {spec.cluster_id: spec.class_name for spec in specs}
    assert "Star" in by_cluster["component_211_5913"]
    assert "radio" not in by_cluster["component_211_5913"].lower()
