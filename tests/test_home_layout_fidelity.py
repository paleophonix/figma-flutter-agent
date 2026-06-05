"""Regression tests for Silent Moon home feed layout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.parser.layout import (
    reconcile_promo_card_row_tops_in_tree,
    reconcile_stack_placement_top_from_edges,
)
from figma_flutter_agent.parser.stack_paint import sort_absolute_stack_children
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing, StackPlacement

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_DUMP_CANDIDATES = (
    _REPO_ROOT.parent / "demo_app" / ".figma_debug" / "processed" / "home_layout.json",
    _REPO_ROOT.parent
    / "flutter-demo-project"
    / "demo_app"
    / ".figma_debug"
    / "processed"
    / "home_layout.json",
)


def _demo_dump_path() -> Path | None:
    for candidate in _DEMO_DUMP_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _load_demo_tree() -> CleanDesignTreeNode | None:
    dump_path = _demo_dump_path()
    if dump_path is None:
        return None
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload["cleanTree"])


def _find(node_id: str, node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find(node_id, child)
        if found is not None:
            return found
    return None


def test_top_reconcile_preserves_promo_card_bbox_top() -> None:
    placement = StackPlacement(
        vertical="TOP",
        left=217.0,
        top=168.0,
        right=20.0,
        bottom=474.0,
        width=177.0,
        height=210.0,
    )
    result = reconcile_stack_placement_top_from_edges(placement, parent_height=896.0)
    assert result.top == 168.0


def test_bottom_nav_shell_paints_before_icons() -> None:
    nav_shell = CleanDesignTreeNode(
        id="nav-shell",
        name="Bottom bar",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=414.0, height=112.0),
        style=NodeStyle(background_color="0xFFFFFFFF"),
        stack_placement=StackPlacement(left=0.0, top=740.0, width=414.0, height=112.0),
    )
    nav_icon = CleanDesignTreeNode(
        id="nav-icon",
        name="Home tab",
        type=NodeType.STACK,
        sizing=Sizing(width=58.0, height=54.0),
        stack_placement=StackPlacement(left=32.0, top=806.0, width=58.0, height=54.0),
        children=[],
    )
    card = CleanDesignTreeNode(
        id="card",
        name="Card",
        type=NodeType.STACK,
        sizing=Sizing(width=177.0, height=210.0),
        stack_placement=StackPlacement(left=20.0, top=168.0, width=177.0, height=210.0),
    )
    ordered = sort_absolute_stack_children(
        [nav_icon, card, nav_shell],
        is_layout_root=True,
    )
    assert [child.id for child in ordered] == ["card", "nav-shell", "nav-icon"]


def test_home_promo_cards_share_row_baseline() -> None:
    tree = _load_demo_tree()
    if tree is None:
        pytest.skip("demo_app processed dump not available")
    updated = reconcile_promo_card_row_tops_in_tree(tree)
    basics = _find("1:6", updated)
    relaxation = _find("1:175", updated)
    assert basics is not None and relaxation is not None
    assert basics.stack_placement is not None and relaxation.stack_placement is not None
    assert basics.stack_placement.top == relaxation.stack_placement.top == 168.0


def test_home_layout_renders_side_by_side_promo_cards() -> None:
    tree = _load_demo_tree()
    if tree is None:
        pytest.skip("demo_app processed dump not available")
    from collections import defaultdict

    from figma_flutter_agent.generator.cluster_variants import collect_cluster_vector_variants
    from figma_flutter_agent.generator.layout.renderer import render_layout_file
    from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs
    from figma_flutter_agent.parser.dedup import prune_decorative_absolute_vectors

    prune_decorative_absolute_vectors(tree)
    cluster_summary: dict[str, int] = defaultdict(int)

    def count(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            cluster_summary[node.cluster_id] += 1
        for child in node.children:
            count(child)

    count(tree)
    specs = collect_cluster_widget_specs(tree, dict(cluster_summary), widget_suffix="Widget")
    variants = collect_cluster_vector_variants(
        [tree],
        {spec.cluster_id: spec.representative for spec in specs},
    )
    classes = {spec.cluster_id: spec.class_name for spec in specs}
    layout = render_layout_file(
        tree,
        feature_name="home",
        uses_svg=True,
        cluster_classes=classes or None,
        cluster_vector_variants=variants or None,
    )["lib/generated/home_layout.dart"]
    assert "top: 168.0" in layout
    assert "top: 212.0" not in layout
    assert "IgnorePointer" in layout
    nav_shell_index = layout.index("key: ValueKey('figma-1_1154')")
    nav_icon_index = layout.index("key: ValueKey('figma-1_1161')")
    assert nav_shell_index < nav_icon_index
