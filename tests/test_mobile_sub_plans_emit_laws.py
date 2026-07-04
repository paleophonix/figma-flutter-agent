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
    assert "TextFormField" not in layout or "Subscribe" not in layout.split("TextFormField", 1)[-1][:200]


def test_star_cluster_delegates_to_star_widget_not_radio() -> None:
    root = _load_root()
    cluster_classes = _cluster_classes(root)
    star = _find_node(root, "240:6321")
    assert star is not None
    assert cluster_classes.get("component_211_5913") == "StarFilledWidget"
    assert resolve_cluster_delegate_class(star, cluster_classes) == "StarFilledWidget"
    layout = _render_layout(root)
    assert "const StarFilledWidget()" in layout
    assert "const RadioButtonWidget()" not in layout


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
    assert "width: 16.0, height: 16.0" in wrapped
    assert "OverflowBox(" in wrapped
    assert "minWidth: 44.0" in wrapped
    assert "SizedBox(width: 44.0, height: 44.0, child: Center" not in wrapped
